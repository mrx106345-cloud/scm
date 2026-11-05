"""Action execution for approved recommendations (Part I2/I4, P4-05/P4-06).

This is the only place a recommendation can leave the system. It enforces, in
order:

1. Role: viewer can never execute.
2. State: the recommendation must be ``approved``. A ``pending`` recommendation
   is auto-approved only when the deterministic autonomy engine says level 3
   allows this exact payload; level 1/2 always require a human decision.
3. Target: the default target is the outbox. Writing to a connector additionally
   requires the global ``SCM_ERP_WRITE_ENABLED`` switch, a registered
   write-capable connector with ``write_enabled`` true, and a PO action type.
4. Audit: every attempt (executed, failed, blocked) is recorded, secrets never
   included.

The LLM is not involved anywhere in this module; the payload is computed data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors import outbox as outbox_service
from app.connectors.registry import build_connector, is_write_capable
from app.core import autonomy
from app.core.audit import append_entry
from app.db.models import Action, Connector, Recommendation

Target = Literal["outbox", "connector"]
Outcome = Literal["executed", "failed", "blocked"]

_EXECUTOR_ROLES = frozenset({"admin", "planner", "purchaser"})
_CONNECTOR_WRITE_ACTIONS = frozenset({"create_draft_po"})


class ExecutionError(ValueError):
    """Raised when an execution request is malformed (not a policy block)."""


@dataclass(frozen=True)
class ExecutionOutcome:
    """What happened to one execution request."""

    status: Outcome
    target: str
    message: str
    action_id: str | None = None
    reference: str | None = None


def _payload(rec: Recommendation) -> dict[str, Any]:
    """Return the effective payload (human edit wins over the computed one)."""
    raw = rec.edited_payload or rec.payload or "{}"
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ExecutionError("recommendation payload is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ExecutionError("recommendation payload must be a JSON object")
    return data


def _record(
    session: Session,
    rec: Recommendation,
    target: str,
    status: Outcome,
    result: dict[str, Any],
    actor_id: str | None,
    reason: str,
) -> Action:
    """Persist one Action row and audit it (never includes secrets)."""
    action = Action(
        recommendation_id=rec.id,
        executed_at=datetime.now(UTC).replace(tzinfo=None),
        target=target,
        result=json.dumps(result, sort_keys=True),
        status=status,
    )
    session.add(action)
    session.flush()
    append_entry(
        session,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id,
        event_type=f"action.{status}",
        entity_type="recommendation",
        entity_id=rec.id,
        payload={
            "action_id": action.id,
            "target": target,
            "status": status,
            "reason": reason,
        },
    )
    session.flush()
    return action


def _blocked(
    session: Session,
    rec: Recommendation,
    target: str,
    actor_id: str | None,
    reason: str,
) -> ExecutionOutcome:
    action = _record(session, rec, target, "blocked", {"reason": reason}, actor_id, reason)
    return ExecutionOutcome(status="blocked", target=target, message=reason, action_id=action.id)


def execute_recommendation(
    session: Session,
    rec_id: str,
    *,
    actor_id: str | None,
    actor_role: str | None,
    target: str = "outbox",
    connector_id: str | None = None,
    now: datetime | None = None,
) -> ExecutionOutcome:
    """Execute one recommendation according to the autonomy policy.

    Returns an ``ExecutionOutcome`` for policy blocks and connector failures;
    raises ``ExecutionError`` only for malformed requests (unknown target).
    """
    if target not in ("outbox", "connector"):
        raise ExecutionError(f"unknown execution target: {target}")

    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise ExecutionError(f"recommendation {rec_id} not found")

    role = (actor_role or "").lower()
    if role not in _EXECUTOR_ROLES:
        return _blocked(session, rec, target, actor_id, f"role {role or 'none'} cannot execute")

    if rec.status == "pending":
        payload = _payload(rec)
        may_execute, level, reason = autonomy.decide_execution(session, rec.action_type, payload)
        if not may_execute:
            return _blocked(session, rec, target, actor_id, f"autonomy level {level}: {reason}")
        rec.status = "approved"
        rec.decided_at = now or datetime.now(UTC).replace(tzinfo=None)
        rec.decided_by = "system:autonomy-l3"
        append_entry(
            session,
            actor_type="system",
            actor_id=None,
            event_type="recommendation.auto_approved",
            entity_type="recommendation",
            entity_id=rec.id,
            payload={"level": level, "reason": reason},
        )
    elif rec.status != "approved":
        return _blocked(
            session, rec, target, actor_id, f"recommendation is {rec.status}, not approved"
        )

    if target == "outbox":
        try:
            ofile = outbox_service.write_export(
                session,
                rec.id,
                "xlsx",
                actor_id=actor_id,
                actor_role=actor_role,
                now=now,
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            rec.status = "failed"
            return _blocked(session, rec, target, actor_id, f"outbox export failed: {exc}")
        rec.status = "executed"
        action = _record(
            session,
            rec,
            target,
            "executed",
            {"file_id": ofile.id, "filename": ofile.filename},
            actor_id,
            "approved recommendation exported to outbox",
        )
        return ExecutionOutcome(
            status="executed",
            target=target,
            message="exported to outbox",
            action_id=action.id,
            reference=ofile.filename,
        )

    # ---- connector write-back: every gate must pass -----------------------
    if not settings.erp_write_enabled:
        return _blocked(session, rec, target, actor_id, "erp write is disabled by configuration")
    if rec.action_type not in _CONNECTOR_WRITE_ACTIONS:
        return _blocked(
            session, rec, target, actor_id, f"{rec.action_type} has no connector write path"
        )
    if not connector_id:
        return _blocked(session, rec, target, actor_id, "connector_id is required")
    connector_row = session.get(Connector, connector_id)
    if connector_row is None:
        return _blocked(session, rec, target, actor_id, "connector not found")
    if not connector_row.write_enabled:
        return _blocked(session, rec, target, actor_id, "connector write is not enabled")
    if not is_write_capable(connector_row.type):
        return _blocked(
            session, rec, target, actor_id, f"connector type {connector_row.type} is read-only"
        )

    payload = _payload(rec)
    try:
        connector = build_connector(connector_row)
        write_result = connector.write(session, payload)
    except Exception as exc:  # noqa: BLE001 - connector errors surface as failed actions
        rec.status = "failed"
        _record(session, rec, target, "failed", {"error": str(exc)}, actor_id, str(exc))
        return ExecutionOutcome(status="failed", target=target, message=str(exc))

    if not write_result.ok:
        rec.status = "failed"
        _record(
            session,
            rec,
            target,
            "failed",
            {"reference": write_result.reference, "message": write_result.message},
            actor_id,
            write_result.message or "connector write failed",
        )
        return ExecutionOutcome(
            status="failed",
            target=target,
            message=write_result.message or "connector write failed",
            reference=write_result.reference,
        )

    rec.status = "executed"
    action = _record(
        session,
        rec,
        target,
        "executed",
        {"reference": write_result.reference, "message": write_result.message},
        actor_id,
        "approved recommendation written to connector",
    )
    return ExecutionOutcome(
        status="executed",
        target=target,
        message=write_result.message or "written to connector",
        action_id=action.id,
        reference=write_result.reference,
    )


def list_actions(session: Session, recommendation_id: str | None = None) -> list[Action]:
    """List action attempts, newest first, optionally for one recommendation."""
    stmt = select(Action).order_by(Action.executed_at.desc(), Action.id)
    if recommendation_id is not None:
        stmt = stmt.where(Action.recommendation_id == recommendation_id)
    return list(session.scalars(stmt))
