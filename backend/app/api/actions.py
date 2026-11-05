"""Action execution API (api-spec A5/A15, P4-05/P4-06).

Thin routes over app/agents/action_agent.py. Roles: admin, planner and
purchaser may execute; viewer is denied. Every attempt is audited by the
service layer, including blocked attempts.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.agents import action_agent
from app.core.dependencies import require_role
from app.db.models import Action, Recommendation
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")

_EXECUTOR = require_role("purchaser")


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Literal["outbox", "connector"] = "outbox"
    connector_id: str | None = None


class ExecuteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    target: str
    message: str
    action_id: str | None = None
    reference: str | None = None
    recommendation_status: str


class ActionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    recommendation_id: str
    executed_at: str | None = None
    target: str
    status: str
    result: str | None = None


def _action_out(action: Action) -> ActionOut:
    return ActionOut(
        id=action.id,
        recommendation_id=action.recommendation_id,
        executed_at=action.executed_at.isoformat() if action.executed_at else None,
        target=action.target,
        status=action.status,
        result=action.result,
    )


@router.post("/recommendations/{rec_id}/execute", response_model=ExecuteResponse)
def execute_recommendation(
    rec_id: str,
    body: ExecuteRequest,
    user: dict[str, str | None] = Depends(_EXECUTOR),  # noqa: B008
) -> ExecuteResponse:
    """Execute an approved recommendation to the outbox or a connector."""
    session = SessionLocal()
    try:
        try:
            outcome = action_agent.execute_recommendation(
                session,
                rec_id,
                actor_id=user.get("id"),
                actor_role=user.get("role"),
                target=body.target,
                connector_id=body.connector_id,
            )
        except action_agent.ExecutionError as exc:
            msg = str(exc)
            status_code = 404 if "not found" in msg else 400
            raise HTTPException(status_code=status_code, detail=msg) from exc
        session.commit()
        rec = session.get(Recommendation, rec_id)
        return ExecuteResponse(
            status=outcome.status,
            target=outcome.target,
            message=outcome.message,
            action_id=outcome.action_id,
            reference=outcome.reference,
            recommendation_status=rec.status if rec else "unknown",
        )
    finally:
        session.close()


@router.get("/recommendations/{rec_id}/actions", response_model=list[ActionOut])
def list_recommendation_actions(
    rec_id: str,
    user: dict[str, str | None] = Depends(_EXECUTOR),  # noqa: B008
) -> list[ActionOut]:
    """List every execution attempt for one recommendation, newest first."""
    session = SessionLocal()
    try:
        if session.get(Recommendation, rec_id) is None:
            raise HTTPException(status_code=404, detail="recommendation not found")
        return [_action_out(a) for a in action_agent.list_actions(session, rec_id)]
    finally:
        session.close()
