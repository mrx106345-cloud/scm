"""Alerts + items + pipeline endpoints (api-spec A4/A6 subset, P1-11).

Thin routes: validate input, check role placeholder, return typed models.
Services/DB wiring lands with the P1-11+ persistence pass; these return
contract-correct shapes so frontend + contract tests proceed.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.db.models import Alert, Item, Supplier
from app.db.session import SessionLocal
from app.llm.explainer import explain_alert as llm_explain_alert
from app.llm.facts import AlertExplanationFacts

router = APIRouter(prefix="/api/v1")


class AlertSummary(BaseModel):
    """Alert list row per api-spec A4."""

    model_config = ConfigDict(extra="forbid")

    id: str
    display_id: int
    type: str
    severity: str
    status: str
    score: str
    item_sku: str = ""


class Page(BaseModel):
    """Paginated envelope."""

    model_config = ConfigDict(extra="forbid")

    items: list[object]
    page: int
    page_size: int
    total: int


@router.get("/alerts")
def list_alerts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> Page:
    """List alerts with pagination (filters land with persistence)."""
    return Page(items=[], page=page, page_size=page_size, total=0)


@router.get("/items")
def list_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> Page:
    """List items with pagination."""
    return Page(items=[], page=page, page_size=page_size, total=0)


class RunRequest(BaseModel):
    """Manual pipeline trigger."""

    model_config = ConfigDict(extra="forbid")


@router.post("/pipeline/run", status_code=202)
def trigger_run() -> dict[str, str]:
    """Trigger a pipeline run (queued; worker executes in P1-10 full)."""
    return {"status": "queued"}


@router.get("/pipeline/runs")
def list_runs() -> Page:
    """List pipeline runs."""
    return Page(items=[], page=1, page_size=25, total=0)


class ExplanationResponse(BaseModel):
    """Alert explanation with source/validator disclosure (Part M §4 badge).

    Deterministic offline text only; ``source`` reports `llm` or `template`
    per H3, so the UI can badge every explanation honestly.
    """

    model_config = ConfigDict(extra="forbid")

    alert_id: str
    summary: str
    why: str
    suggested_action: str
    source: str
    validator: str
    facts: dict[str, object]


def _facts_for_alert(alert: Alert) -> AlertExplanationFacts:
    """Build computed AlertExplanationFacts from joined masters (code only)."""
    session = SessionLocal()
    try:
        item = session.get(Item, alert.item_id) if alert.item_id else None
        supplier = session.get(Supplier, alert.supplier_id) if alert.supplier_id else None
        return AlertExplanationFacts(
            item_name=item.name if item else "",
            site=str(alert.site_id or ""),
            on_hand=0.0,
            days_to_stockout=0.0,
            supplier_name=supplier.name if supplier else "",
            lead_time_days=float(
                supplier.contract_lead_time_days
                if supplier and supplier.contract_lead_time_days
                else 0.0
            ),
            stockout_probability_pct=0.0,
            expected_loss=f"{float(alert.expected_loss):.2f}",
            suggested_qty=0.0,
            extra_cost="0.00",
            severity=alert.severity,
            alert_type=alert.type,
        )
    finally:
        session.close()


@router.get("/alerts/{alert_id}/explanation")
def alert_explanation(alert_id: str) -> ExplanationResponse:
    """Return the deterministic alert explanation (template-backed offline)."""
    session = SessionLocal()
    try:
        alert = session.get(Alert, alert_id)
    finally:
        session.close()
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    facts = _facts_for_alert(alert)
    # Offline deterministic path: template facts route through the H3
    # retry/validate pipeline with a backend whose output the validator
    # rejects, forcing source="template" without needing a model file.
    from app.llm.backends import MockBackend

    result = llm_explain_alert(facts, MockBackend(canned_summary="UNMATCHED 999999"))
    return ExplanationResponse(
        alert_id=alert_id,
        summary=str(result["summary"]),
        why=str(result["why"]),
        suggested_action=str(result["suggested_action"]),
        source=str(result["source"]),
        validator=str(result["validator"]),
        facts={k: v for k, v in facts.to_json_dict().items()},
    )
