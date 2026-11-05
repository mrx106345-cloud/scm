"""Autonomy settings and level-3 gates (Part I.1, P4-05).

Levels are stored per action type in ``settings`` as ``autonomy.<action_type>``
(JSON number). Level 3 additionally needs:
  * every limit configured: max_value_per_action, max_qty, allowed_supplier_ids,
    allowed_item_criticality, daily_action_cap;
  * the install to be at least ``settings.autonomy_min_days`` old;
  * an explicit Admin acknowledgment recorded in the audit log.

Anything outside the limits at level 3 falls back to level 2 (approval), never
to silent execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.audit import append_entry
from app.db.models import Action, Setting

ACTION_TYPES = ("create_draft_po", "raise_reorder_request", "draft_supplier_message")
LEVEL_MIN, LEVEL_MAX = 1, 3

LIMIT_KEYS = (
    "max_value_per_action",
    "max_qty",
    "allowed_supplier_ids",
    "allowed_item_criticality",
    "daily_action_cap",
)


class AutonomyError(ValueError):
    """Raised when an autonomy change is not allowed."""


@dataclass(frozen=True)
class AutonomyStatus:
    """Resolved autonomy state for one action type."""

    action_type: str
    level: int
    limits: dict[str, Any]
    level3_ready: bool
    reasons: tuple[str, ...]


def _get_setting(session: Session, key: str) -> str | None:
    row = session.get(Setting, key)
    return row.value if row is not None else None


def _put_setting(session: Session, key: str, value: str, updated_by: str | None) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(
            Setting(
                key=key,
                value=value,
                updated_by=updated_by,
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
    else:
        row.value = value
        row.updated_by = updated_by
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)


def get_level(session: Session, action_type: str) -> int:
    """Return the configured level (1 when unset), validated to 1..3."""
    if action_type not in ACTION_TYPES:
        raise AutonomyError(f"unknown action type: {action_type}")
    raw = _get_setting(session, f"autonomy.{action_type}")
    if raw is None:
        return 1
    try:
        level = int(json.loads(raw))
    except (TypeError, ValueError):
        return 1
    return level if LEVEL_MIN <= level <= LEVEL_MAX else 1


def get_limits(session: Session) -> dict[str, Any]:
    """Return the level-3 limits JSON (empty dict when unset)."""
    raw = _get_setting(session, "autonomy.limits")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def install_age_days(session: Session) -> int:
    """Days since the install marker (first run), 0 when unknown."""
    raw = _get_setting(session, "system.installed_at")
    if not raw:
        return 0
    try:
        installed = datetime.fromisoformat(raw)
    except ValueError:
        return 0
    if installed.tzinfo is None:
        installed = installed.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - installed).days)


def _missing_limits(limits: dict[str, Any]) -> list[str]:
    missing = []
    for key in LIMIT_KEYS:
        value = limits.get(key)
        if value is None or (isinstance(value, (list, str)) and len(value) == 0):
            missing.append(key)
    return missing


def level3_readiness(session: Session) -> AutonomyStatus:
    """Evaluate whether level 3 may be enabled right now."""
    limits = get_limits(session)
    missing = _missing_limits(limits)
    reasons: list[str] = []
    if missing:
        reasons.append("missing limits: " + ", ".join(missing))
    age = install_age_days(session)
    if age < settings.autonomy_min_days:
        reasons.append(
            f"system has run {age} days; level 3 needs {settings.autonomy_min_days}"
        )
    return AutonomyStatus(
        action_type="*",
        level=0,
        limits=limits,
        level3_ready=not reasons,
        reasons=tuple(reasons),
    )


def set_level(
    session: Session,
    action_type: str,
    level: int,
    actor_id: str | None,
    acknowledge_level3: bool = False,
) -> AutonomyStatus:
    """Set the autonomy level with the Part I.1 gates; audited by the caller."""
    if action_type not in ACTION_TYPES:
        raise AutonomyError(f"unknown action type: {action_type}")
    if level < LEVEL_MIN or level > LEVEL_MAX:
        raise AutonomyError("level must be 1, 2 or 3")
    if level == 3:
        readiness = level3_readiness(session)
        if not readiness.level3_ready:
            raise AutonomyError("; ".join(readiness.reasons))
        if not acknowledge_level3:
            raise AutonomyError("level 3 requires an explicit acknowledgment")
        _put_setting(session, "autonomy.level3_ack", "true", actor_id)
        record_level3_ack(session, actor_id)
    _put_setting(session, f"autonomy.{action_type}", json.dumps(level), actor_id)
    return AutonomyStatus(
        action_type=action_type,
        level=level,
        limits=get_limits(session),
        level3_ready=level3_readiness(session).level3_ready,
        reasons=(),
    )


def set_limits(session: Session, limits: dict[str, Any], actor_id: str | None) -> None:
    """Validate and store the five level-3 limits."""
    unknown = set(limits) - set(LIMIT_KEYS)
    if unknown:
        raise AutonomyError("unknown limit keys: " + ", ".join(sorted(unknown)))
    cleaned: dict[str, Any] = {}
    for key in LIMIT_KEYS:
        if key not in limits:
            continue
        value = limits[key]
        if key in ("max_value_per_action", "max_qty", "daily_action_cap"):
            try:
                number = Decimal(str(value))
            except (InvalidOperation, TypeError) as exc:
                raise AutonomyError(f"{key} must be numeric") from exc
            if number <= 0:
                raise AutonomyError(f"{key} must be positive")
            cleaned[key] = float(number)
        elif key == "allowed_supplier_ids":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise AutonomyError("allowed_supplier_ids must be a list of ids")
            cleaned[key] = value
        elif key == "allowed_item_criticality":
            if not isinstance(value, list) or not set(value) <= {"A", "B", "C"}:
                raise AutonomyError("allowed_item_criticality must be a subset of A,B,C")
            cleaned[key] = value
    _put_setting(session, "autonomy.limits", json.dumps(cleaned), actor_id)


def _within_limits(
    session: Session, payload: dict[str, Any], limits: dict[str, Any]
) -> tuple[bool, str]:
    """Check one proposed action against the five limits."""
    try:
        value = Decimal(str(payload.get("est_cost", payload.get("value", 0)) or 0))
    except (InvalidOperation, TypeError):
        return False, "value not numeric"
    if value > Decimal(str(limits["max_value_per_action"])):
        return False, "value over max_value_per_action"
    try:
        qty = Decimal(str(payload.get("qty", payload.get("quantity", 0)) or 0))
    except (InvalidOperation, TypeError):
        return False, "qty not numeric"
    if qty > Decimal(str(limits["max_qty"])):
        return False, "qty over max_qty"
    supplier = str(payload.get("supplier_id", ""))
    if supplier and supplier not in limits["allowed_supplier_ids"]:
        return False, "supplier not allowed"
    criticality = str(payload.get("criticality", ""))
    if criticality and criticality not in limits["allowed_item_criticality"]:
        return False, "criticality not allowed"
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    count = session.scalar(
        select(func.count())
        .select_from(Action)
        .where(Action.executed_at >= since, Action.status == "executed")
    )
    if int(count or 0) >= int(limits["daily_action_cap"]):
        return False, "daily action cap reached"
    return True, "ok"


def decide_execution(
    session: Session, action_type: str, payload: dict[str, Any]
) -> tuple[bool, int, str]:
    """Return (may_execute_without_approval, level, reason).

    Level 1 never executes. Level 2 always needs a human approval. Level 3
    executes automatically only when every limit passes; otherwise the caller
    must fall back to approval (level 2 behavior).
    """
    level = get_level(session, action_type)
    if level == 1:
        return False, level, "level 1 is advise-only"
    if level == 2:
        return False, level, "level 2 requires approval"
    limits = get_limits(session)
    if _missing_limits(limits):
        return False, level, "level 3 limits incomplete"
    ok, reason = _within_limits(session, payload, limits)
    if not ok:
        return False, level, f"outside limits: {reason}"
    return True, level, "within level 3 limits"


def record_level3_ack(session: Session, actor_id: str | None) -> None:
    """Record the required level-3 acknowledgment in the audit log."""
    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type="autonomy.level3_acknowledged",
        entity_type="settings",
        entity_id="autonomy",
        payload={"acknowledged": True},
    )
