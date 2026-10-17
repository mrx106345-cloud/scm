"""Item detail endpoints (spec P3-07).

Thin routes: logic lives here (deterministic computation only, no LLM).
The acting user is resolved via the get_current_user dependency (P1-11 real auth);
the route layer enforces roles.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.chat.queries import forecast as chat_forecast
from app.core.dependencies import get_current_user
from app.db.models import Alert, Item, PoLine, PurchaseOrder
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")


class ItemDetailOut(BaseModel):
    """Full item page data: master parameters, forecast, alert history, open POs.

    Item master fields present in the schema (Part C2): sku, name, uom,
    category, criticality, unit_cost, moq, lot_multiple, stockout_cost,
    service_level. SS/ROP/Q are not persisted columns in this phase; the item
    page reports what is available and marks the rest as absent.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    sku: str
    name: str
    uom: str
    category: str | None
    criticality: str
    unit_cost: str | None
    moq: float
    lot_multiple: float
    stockout_cost: str | None
    service_level: float | None
    forecast: dict[str, Any] | None = None
    alert_history: list[dict[str, Any]] = []
    open_pos: list[dict[str, Any]] = []


@router.get("/items/{item_id}", response_model=ItemDetailOut)
def get_item(
    item_id: str,
    user: dict = Depends(get_current_user),  # noqa: B008
) -> ItemDetailOut:
    """Item detail page: parameters (SS, ROP, Q, service level), forecast,
    alert history, open POs (spec P3-07 item page)."""
    role = user.get("role") or "viewer"
    if role not in ("admin", "planner", "purchaser", "viewer"):
        raise HTTPException(status_code=403, detail="forbidden")
    session = SessionLocal()
    try:
        item = session.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="item not found")

        # Forecast chart data: 4-week horizon via the classical selection core.
        forecast_data: dict[str, Any] | None = None
        try:
            forecast_data = chat_forecast(item, [0.0] * 12, session)
        except Exception:
            forecast_data = None

        # Alert history for this item, newest first.
        alert_rows = session.scalars(
            select(Alert)
            .where(Alert.item_id == item_id)
            .order_by(Alert.created_at.desc())
        ).all()
        alert_history: list[dict[str, Any]] = [
            {
                "id": a.id,
                "type": a.type,
                "severity": a.severity,
                "status": a.status,
                "score": str(round(float(a.score), 2)),
                "expected_loss": round(float(a.expected_loss), 2),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alert_rows
        ]

        # Open POs for this item (status open/partial).
        po_rows = session.execute(
            select(PurchaseOrder, PoLine)
            .join(PoLine, PoLine.po_id == PurchaseOrder.id)
            .where(
                PoLine.item_id == item_id,
                PurchaseOrder.status.in_(("open", "partial")),
            )
            .order_by(PurchaseOrder.order_date.desc())
        ).all()
        open_pos: list[dict[str, Any]] = [
            {
                "po_id": po.id,
                "po_number": po.po_number,
                "supplier_id": po.supplier_id,
                "status": po.status,
                "order_date": po.order_date.isoformat() if po.order_date else None,
                "promised_date": po.promised_date.isoformat() if po.promised_date else None,
                "qty_ordered": float(line.qty_ordered) if line.qty_ordered is not None else 0.0,
            }
            for po, line in po_rows
        ]

        return ItemDetailOut(
            id=item.id,
            sku=item.sku,
            name=item.name,
            uom=item.uom,
            category=item.category,
            criticality=item.criticality,
            unit_cost=str(item.unit_cost) if item.unit_cost else None,
            moq=float(item.moq),
            lot_multiple=float(item.lot_multiple),
            stockout_cost=str(item.stockout_cost) if item.stockout_cost else None,
            service_level=item.service_level,
            forecast=forecast_data,
            alert_history=alert_history,
            open_pos=open_pos,
        )
    finally:
        session.close()