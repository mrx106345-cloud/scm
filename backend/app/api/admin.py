"""Autonomy administration API (Part I.1, P4-05).

Admin-only. Level 3 is refused unless all five limits are set, the install is
at least ``SCM_AUTONOMY_MIN_DAYS`` old and the admin explicitly acknowledges
the risk; that acknowledgment is itself audited.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.core import autonomy
from app.core.audit import append_entry
from app.core.dependencies import require_role
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")

_ADMIN = require_role("admin")


class AutonomyLevelOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    level: int


class AutonomyOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_types: list[AutonomyLevelOut]
    limits: dict[str, Any]
    level3_ready: bool
    reasons: list[str]
    install_age_days: int
    autonomy_min_days: int
    erp_write_enabled: bool
    zoho_enabled: bool


class LevelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1, le=3)
    acknowledge: bool = False


def _status(session: Any) -> AutonomyOut:
    readiness = autonomy.level3_readiness(session)
    return AutonomyOut(
        action_types=[
            AutonomyLevelOut(action_type=t, level=autonomy.get_level(session, t))
            for t in autonomy.ACTION_TYPES
        ],
        limits=autonomy.get_limits(session),
        level3_ready=readiness.level3_ready,
        reasons=list(readiness.reasons),
        install_age_days=autonomy.install_age_days(session),
        autonomy_min_days=settings.autonomy_min_days,
        erp_write_enabled=settings.erp_write_enabled,
        zoho_enabled=settings.zoho_enabled,
    )


@router.get("/admin/autonomy", response_model=AutonomyOut)
def get_autonomy(
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> AutonomyOut:
    """Return levels, limits and why level 3 is or is not available."""
    session = SessionLocal()
    try:
        return _status(session)
    finally:
        session.close()


@router.put("/admin/autonomy/limits", response_model=AutonomyOut)
def put_limits(
    body: dict[str, Any],
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> AutonomyOut:
    """Set the five level-3 limits (unknown keys are rejected)."""
    session = SessionLocal()
    try:
        try:
            autonomy.set_limits(session, body, user.get("id"))
        except autonomy.AutonomyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        append_entry(
            session,
            actor_type="user",
            actor_id=user.get("id"),
            event_type="autonomy.limits_changed",
            entity_type="settings",
            entity_id="autonomy",
            payload={"limits": autonomy.get_limits(session)},
        )
        session.commit()
        return _status(session)
    finally:
        session.close()


@router.put("/admin/autonomy/{action_type}", response_model=AutonomyOut)
def put_level(
    action_type: str,
    body: LevelRequest,
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> AutonomyOut:
    """Set one action type's autonomy level (level 3 has hard gates)."""
    session = SessionLocal()
    try:
        previous = autonomy.get_level(session, action_type)
        try:
            autonomy.set_level(
                session,
                action_type,
                body.level,
                user.get("id"),
                acknowledge_level3=body.acknowledge,
            )
        except autonomy.AutonomyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        append_entry(
            session,
            actor_type="user",
            actor_id=user.get("id"),
            event_type="autonomy.level_changed",
            entity_type="settings",
            entity_id=action_type,
            payload={"previous_level": previous, "new_level": body.level},
        )
        session.commit()
        return _status(session)
    finally:
        session.close()
