"""Chat endpoint (Part H4, spec `llm/intents.py, api/chat.py`).

Thin route: match the question to a fixed read-only intent, dispatch to the
chat query functions, return structured facts. The chat path is read-only --
it never takes writes, never runs arbitrary SQL, and never exposes data the
user's role may not see (all six chat intents are viewer-visible per I4).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.queries import (
    explain_alert,
    forecast,
    item_status,
    list_alerts,
    savings_report,
    supplier_summary,
)
from app.db.models import Item, Supplier
from app.db.session import SessionLocal
from app.llm.intents import (
    INTENT_EXPLAIN_ALERT,
    INTENT_FORECAST,
    INTENT_ITEM_STATUS,
    INTENT_LIST_ALERTS,
    INTENT_SAVINGS_REPORT,
    INTENT_SUPPLIER_SUMMARY,
    SUPPORTED_INTENTS,
    ParsedQuery,
    match,
)

router = APIRouter(prefix="/api/v1")

SUPPORTED_QUESTIONS: tuple[str, ...] = (
    "How is item <sku/name> doing? (item_status)",
    "What is the forecast for <sku/name>? (forecast)",
    "List critical/high alerts (list_alerts)",
    "Explain alert <id> (explain_alert)",
    "Tell me about supplier <name> (supplier_summary)",
    "How much have we saved last quarter? (savings_report)",
)


class ChatAskRequest(BaseModel):
    """Free-text ask. The matcher decides the query; users cannot pick it.

    Asking a question never writes. Role enforcement is deny-by-default at the
    next layer; all six chat intents are viewer-visible per spec I4.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)


class ChatAskResponse(BaseModel):
    """Structured facts for one ask."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    entity: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    table: list[dict[str, Any]] = Field(default_factory=list)
    supported_questions: list[str] = Field(default_factory=list)


def _find_item(session: Session, target: str | None) -> Item | None:
    """Resolve an extracted item target to the closest master row."""
    if not target:
        return None
    target_l = target.lower().strip()
    items = session.scalars(select(Item)).all()
    for item in items:
        if item.sku.lower() == target_l or item.name.lower() == target_l:
            return item
    for item in items:
        if target_l in item.sku.lower() or target_l in item.name.lower():
            return item
    try:
        from rapidfuzz import fuzz

        best: Item | None = None
        best_score = 0.0
        for item in items:
            for cand in (item.name.lower(), item.sku.lower()):
                score = fuzz.ratio(cand, target_l)
                if score > best_score:
                    best_score = score
                    best = item
        return best if best_score >= 60.0 else None
    except ImportError:
        return None


def _find_supplier(session: Session, target: str | None) -> Supplier | None:
    """Resolve an extracted supplier target to the closest master row."""
    if not target:
        return None
    target_l = target.lower().strip()
    suppliers = session.scalars(select(Supplier)).all()
    for sup in suppliers:
        if sup.name.lower() == target_l or sup.code.lower() == target_l:
            return sup
    for sup in suppliers:
        if target_l in sup.name.lower():
            return sup
    return None


def ask(question: str) -> ChatAskResponse:
    """Run one question through match -> fixed query -> facts (read-only)."""
    pq: ParsedQuery = match(question)
    if pq.intent not in SUPPORTED_INTENTS:
        return ChatAskResponse(
            intent="unknown",
            entity=None,
            facts={},
            table=[],
            supported_questions=list(SUPPORTED_QUESTIONS),
        )
    session = SessionLocal()
    try:
        if pq.intent == INTENT_ITEM_STATUS:
            item = _find_item(session, pq.entity)
            if item is None:
                raise HTTPException(status_code=404, detail="item not found")
            facts = item_status(item, session)
            return ChatAskResponse(
                intent=pq.intent, entity=pq.entity, facts=facts, table=[facts["item"]]
            )
        if pq.intent == INTENT_FORECAST:
            item = _find_item(session, pq.entity)
            if item is None:
                raise HTTPException(status_code=404, detail="item not found")
            facts = forecast(item, [0.0] * 12, session)
            table = [{"week": i + 1, "qty": v} for i, v in enumerate(facts["forecast"])]
            return ChatAskResponse(intent=pq.intent, entity=pq.entity, facts=facts, table=table)
        if pq.intent == INTENT_LIST_ALERTS:
            filters: dict[str, str] = {}
            for part in (pq.entity or "").split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    filters[k.strip()] = v.strip()
            facts = list_alerts(filters.get("severity"), filters.get("supplier"), session)
            return ChatAskResponse(
                intent=pq.intent,
                entity=pq.entity,
                facts=facts,
                table=list(facts["alerts"]),
            )
        if pq.intent == INTENT_EXPLAIN_ALERT:
            facts = explain_alert(pq.entity or "", session)
            return ChatAskResponse(
                intent=pq.intent,
                entity=pq.entity,
                facts=facts,
                table=[facts["alert"]] if facts.get("alert") else [],
            )
        if pq.intent == INTENT_SUPPLIER_SUMMARY:
            supplier = _find_supplier(session, pq.entity)
            if supplier is None:
                raise HTTPException(status_code=404, detail="supplier not found")
            facts = supplier_summary(supplier, session)
            return ChatAskResponse(
                intent=pq.intent, entity=pq.entity, facts=facts, table=[facts["supplier"]]
            )
        if pq.intent == INTENT_SAVINGS_REPORT:
            period = pq.entity or "this_year"
            facts = savings_report(period, session)
            return ChatAskResponse(intent=pq.intent, entity=pq.entity, facts=facts, table=[facts])
    finally:
        session.close()
    raise HTTPException(status_code=400, detail="unsupported intent")


@router.post("/chat/ask")
def chat_ask(req: ChatAskRequest) -> ChatAskResponse:
    """Answer a free-text question via match -> fixed query -> facts."""
    return ask(req.question)
