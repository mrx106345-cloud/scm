"""Approval service (Part I2/I4, P3-04): recommendation state machine + role enforcement.

Pure decision logic; routes stay thin. Every state transition is written to the
tamper-evident audit log with the acting user. No LLM, no outbound calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import append_entry
from app.db.models import Recommendation

Decision = Literal["approve", "reject", "edit_approve"]

# Part I2 state machine: pending -> approved/rejected/cancelled; everything else
# is terminal (approved, rejected, executed, failed, cancelled).
_TRANSITION_TARGETS: dict[str, frozenset[str]] = {
    "pending": frozenset({"approved", "rejected", "cancelled"}),
}

# Part I4: a purchaser may only decide PO and message action types.
_PURCHASER_ALLOWED = frozenset({"create_draft_po", "draft_supplier_message"})
_APPROVER_ROLES = frozenset({"admin", "planner"})


class TransitionError(ValueError):
    """Rejected state transition or unauthorized decision."""


def _require_role(actor_role: str, action_type: str) -> None:
    role = (actor_role or "viewer").lower()
    if role not in _APPROVER_ROLES and role != "purchaser":
        raise TransitionError(f"role {actor_role!r} cannot decide recommendations")
    if role == "purchaser" and action_type not in _PURCHASER_ALLOWED:
        raise TransitionError(f"purchaser cannot decide {action_type}")


def decide(
    session: Session,
    rec_id: str,
    decision: Decision,
    actor_id: str,
    actor_role: str,
    edited_payload: str | None = None,
    comment: str | None = None,
) -> Recommendation:
    """Apply a human decision to a pending recommendation (Part I2/I4).

    Transitions: ``pending -> approved`` / ``rejected`` / ``cancelled``.
    ``edit_approve`` stores the edited payload before approving.
    Raises ``TransitionError`` on invalid transitions or unauthorized roles.
    Every transition is audited with the actor.
    """
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise TransitionError(f"recommendation {rec_id} not found")
    if rec.status != "pending":
        raise TransitionError(f"recommendation {rec_id} is {rec.status}, not pending")
    _require_role(actor_role, rec.action_type)

    now = datetime.now(UTC)
    rec.decided_at = now
    rec.decided_by = actor_id
    rec.decision_comment = comment
    if decision == "edit_approve":
        if edited_payload is not None:
            rec.edited_payload = edited_payload
        rec.status = "approved"
        event_type = "recommendation.edit_approve"
    elif decision == "approve":
        rec.status = "approved"
        event_type = "recommendation.approved"
    elif decision == "reject":
        rec.status = "rejected"
        event_type = "recommendation.rejected"
    else:  # pragma: no cover - Literal excludes other values at static-check time
        raise TransitionError(f"unknown decision {decision!r}")

    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type=event_type,
        entity_type="recommendation",
        entity_id=rec.id,
        payload={
            "decision": decision,
            "action_type": rec.action_type,
            "previous_status": "pending",
            "new_status": rec.status,
            "comment": comment,
        },
    )
    session.flush()
    return rec


def list_recommendations(
    session: Session,
    status: str | None = None,
    action_type: str | None = None,
) -> list[Recommendation]:
    """List recommendations, optionally filtered by status and/or action type."""
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc(), Recommendation.id)
    if status is not None:
        stmt = stmt.where(Recommendation.status == status)
    if action_type is not None:
        stmt = stmt.where(Recommendation.action_type == action_type)
    return list(session.scalars(stmt))
