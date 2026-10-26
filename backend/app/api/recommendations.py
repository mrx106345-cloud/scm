"""Recommendation list + decision endpoints (api-spec A5, P3-04).

Thin routes: logic lives in app/agents/approval_agent.py. The acting user is
resolved via the get_current_user dependency (P1-11 real auth); the service layer
enforces roles and audits every transition regardless.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.agents import approval_agent
from app.core.dependencies import get_current_user
from app.db.models import Alert, Recommendation
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")

DecisionValue = Literal["approve", "reject", "edit_approve"]


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: DecisionValue
    edited_payload: str | None = None
    comment: str | None = None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    display_id: int
    alert_id: str
    action_type: str
    payload: str | None = None
    est_cost: str | None = None
    est_benefit: str | None = None
    benefit_label: str
    autonomy_level: int
    status: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision_comment: str | None = None
    edited_payload: str | None = None
    created_at: str | None = None


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[object]
    page: int
    page_size: int
    total: int


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: RecommendationOut
    action: dict[str, str]


def _out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        display_id=rec.display_id,
        alert_id=rec.alert_id,
        action_type=rec.action_type,
        payload=rec.payload,
        est_cost=(str(rec.est_cost) if rec.est_cost is not None else None),
        est_benefit=(str(rec.est_benefit) if rec.est_benefit is not None else None),
        benefit_label=rec.benefit_label,
        autonomy_level=rec.autonomy_level,
        status=rec.status,
        decided_at=(rec.decided_at.isoformat() if rec.decided_at is not None else None),
        decided_by=rec.decided_by,
        decision_comment=rec.decision_comment,
        edited_payload=rec.edited_payload,
        created_at=(rec.created_at.isoformat() if rec.created_at is not None else None),
    )


@router.get("/recommendations")
def list_recommendations(
    user: dict[str, str | None] = Depends(get_current_user),  # noqa: B008
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    status: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    supplier_id: str | None = Query(default=None),
) -> Page:
    """List recommendations with optional status/action_type/supplier_id filters."""
    role = user.get("role") or ""
    if role not in ("admin", "planner", "purchaser", "viewer"):
        raise HTTPException(status_code=403, detail="forbidden")
    session = SessionLocal()
    try:
        stmt = select(Recommendation)
        if supplier_id is not None:
            stmt = stmt.join(Alert, Alert.id == Recommendation.alert_id).where(
                Alert.supplier_id == supplier_id
            )
        rows = approval_agent.list_recommendations(session, status=status, action_type=action_type)
        if supplier_id is not None:
            wanted = {r.id for r in session.scalars(stmt).all()}
            rows = [r for r in rows if r.id in wanted]
        total = len(rows)
        start = (page - 1) * page_size
        items: list[object] = []
        items.extend(_out(r) for r in rows[start : start + page_size])
        return Page(items=items, page=page, page_size=page_size, total=total)
    finally:
        session.close()


@router.get("/recommendations/{rec_id}")
def get_recommendation(
    rec_id: str,
    user: dict[str, str | None] = Depends(get_current_user),  # noqa: B008
) -> RecommendationOut:
    role = user.get("role") or ""
    if role not in ("admin", "planner", "purchaser", "viewer"):
        raise HTTPException(status_code=403, detail="forbidden")
    session = SessionLocal()
    try:
        rec = session.get(Recommendation, rec_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="recommendation not found")
        return _out(rec)
    finally:
        session.close()


@router.post("/recommendations/{rec_id}/decision")
def decide_recommendation(
    rec_id: str,
    body: DecisionRequest,
    user: dict[str, str | None] = Depends(get_current_user),  # noqa: B008
) -> DecisionResponse:
    actor_id = user.get("id")
    if actor_id is None:
        raise HTTPException(status_code=401, detail="acting user required")
    role = user.get("role") or ""
    session = SessionLocal()
    try:
        try:
            rec = approval_agent.decide(
                session,
                rec_id,
                body.decision,
                actor_id,
                role,
                edited_payload=body.edited_payload,
                comment=body.comment,
            )
        except approval_agent.TransitionError as exc:
            msg = str(exc)
            if "not found" in msg:
                raise HTTPException(status_code=404, detail=msg) from exc
            if "cannot" in msg or "forbidden" in msg.lower():
                raise HTTPException(status_code=403, detail=msg) from exc
            if "not valid JSON" in msg:
                raise HTTPException(status_code=400, detail=msg) from exc
            raise HTTPException(status_code=409, detail=msg) from exc
        session.commit()
        if rec.status == "approved":
            action = {"target": "outbox", "recommendation_id": rec.id}
        else:
            action = {"target": "none", "recommendation_id": rec.id}
        return DecisionResponse(recommendation=_out(rec), action=action)
    finally:
        session.close()
