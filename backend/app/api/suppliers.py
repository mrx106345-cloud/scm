"""Supplier list + detail endpoints (spec P3-07).

Thin routes: logic lives here (deterministic computation only, no LLM).
The acting user is resolved via the get_current_user dependency (P1-11 real auth);
the route layer enforces roles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.dependencies import get_current_user
from app.db.models import (
    Item,
    PoLine,
    PurchaseOrder,
    Receipt,
    Supplier,
    SupplierMetrics,
)
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")


class SupplierMetricOut(BaseModel):
    """One supplier row with latest computed metrics (viewer-visible)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    active: bool
    contract_lead_time_days: int | None = None
    risk_score: int | None = None
    on_time_rate: float | None = None
    mean_lt_recent: float | None = None
    drift_pct: float | None = None
    trend_flag: bool | None = None
    low_data: bool | None = None


class SupplierDetailOut(BaseModel):
    """Full supplier page data: metrics, risk breakdown, lead-time trend, items exposed."""

    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    active: bool
    contract_lead_time_days: int | None = None
    metrics: dict[str, object] | None = None
    risk_breakdown: dict[str, float] | None = None
    lead_time_trend: list[dict[str, object]] = []
    items_exposed: list[dict[str, object]] = []


class Page(BaseModel):
    """Paginated envelope."""

    model_config = ConfigDict(extra="forbid")

    items: list[object]
    page: int
    page_size: int
    total: int


@router.get("/suppliers", response_model=Page)
def list_suppliers(
    user: dict = Depends(get_current_user),  # noqa: B008
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> Page:
    """List suppliers with latest computed metrics (spec P3-07 supplier page)."""
    role = user.get("role") or "viewer"
    if role not in ("admin", "planner", "purchaser", "viewer"):
        raise HTTPException(status_code=403, detail="forbidden")
    session = SessionLocal()
    try:
        latest_subq = (
            select(
                SupplierMetrics.supplier_id,
                func.max(SupplierMetrics.id).label("latest_id"),
            )
            .group_by(SupplierMetrics.supplier_id)
            .subquery()
        )
        rows = (
            session.execute(
                select(Supplier, SupplierMetrics)
                .outerjoin(
                    latest_subq,
                    Supplier.id == latest_subq.c.supplier_id,
                )
                .outerjoin(
                    SupplierMetrics,
                    SupplierMetrics.id == latest_subq.c.latest_id,
                )
                .order_by(Supplier.code)
            )
        ).all()

        items: list[SupplierMetricOut] = []
        for sup, metrics in rows:
            items.append(
                SupplierMetricOut(
                    id=sup.id,
                    code=sup.code,
                    name=sup.name,
                    active=sup.active,
                    contract_lead_time_days=sup.contract_lead_time_days,
                    risk_score=metrics.risk_score if metrics else None,
                    on_time_rate=metrics.on_time_rate if metrics else None,
                    mean_lt_recent=metrics.mean_lt_recent if metrics else None,
                    drift_pct=metrics.drift_pct if metrics else None,
                    trend_flag=metrics.trend_flag if metrics else None,
                    low_data=None,
                )
            )

        total = len(items)
        start = (page - 1) * page_size
        return Page(
            items=list[object](items[start : start + page_size]),
            page=page,
            page_size=page_size,
            total=total,
        )
    finally:
        session.close()


@router.get("/suppliers/{supplier_id}", response_model=SupplierDetailOut)
def get_supplier(
    supplier_id: str,
    user: dict = Depends(get_current_user),  # noqa: B008
) -> SupplierDetailOut:
    """Supplier detail page: risk breakdown, lead-time trend, items exposed."""
    role = user.get("role") or "viewer"
    if role not in ("admin", "planner", "purchaser", "viewer"):
        raise HTTPException(status_code=403, detail="forbidden")
    session = SessionLocal()
    try:
        sup = session.get(Supplier, supplier_id)
        if sup is None:
            raise HTTPException(status_code=404, detail="supplier not found")

        # Latest metrics row.
        metrics = session.scalars(
            select(SupplierMetrics)
            .where(SupplierMetrics.supplier_id == supplier_id)
            .order_by(SupplierMetrics.id.desc())
        ).first()

        metrics_out: dict[str, object] | None = None
        risk_breakdown: dict[str, float] | None = None
        if metrics is not None:
            metrics_out = {
                "mean_lt_recent": metrics.mean_lt_recent,
                "mean_lt_prior": metrics.mean_lt_prior,
                "drift_pct": metrics.drift_pct,
                "on_time_rate": metrics.on_time_rate,
                "dependency_share": metrics.dependency_share,
                "risk_score": metrics.risk_score,
                "trend_flag": metrics.trend_flag,
                "low_data": None,
            }
            # Risk breakdown per Part F3 formula:
            #   0.40 * clip(drift/0.5) + 0.35 * (1 - on_time_rate) + 0.25 * dependency_share
            drift = float(metrics.drift_pct or 0.0)
            clip = max(0.0, min(1.0, drift / 0.5))
            otr = float(metrics.on_time_rate if metrics.on_time_rate is not None else 1.0)
            dep = float(metrics.dependency_share if metrics.dependency_share is not None else 0.0)
            risk_breakdown = {
                "drift_component": round(0.40 * clip, 4),
                "on_time_component": round(0.35 * (1.0 - otr), 4),
                "dependency_component": round(0.25 * dep, 4),
                "total_raw": round(
                    0.40 * clip + 0.35 * (1.0 - otr) + 0.25 * dep, 4
                ),
            }

        # Lead-time trend: receipt lead days over time (oldest first).
        trend_rows = session.execute(
            select(Receipt.receipt_date, PurchaseOrder.order_date)
            .join(PoLine, Receipt.po_line_id == PoLine.id)
            .join(PurchaseOrder, PoLine.po_id == PurchaseOrder.id)
            .where(PurchaseOrder.supplier_id == supplier_id)
            .order_by(Receipt.receipt_date)
        ).all()
        lead_time_trend: list[dict[str, object]] = []
        for receipt_date, order_date in trend_rows:
            lead_days = (receipt_date - order_date).total_seconds() / 86400.0
            lead_time_trend.append(
                {
                    "receipt_date": receipt_date.isoformat() if receipt_date else None,
                    "lead_days": round(lead_days, 2),
                }
            )

        # Items exposed: open POs (status open/partial) for this supplier with item info.
        exposed_rows = session.execute(
            select(Item, PurchaseOrder.po_number, PurchaseOrder.status, PoLine.qty_ordered)
            .join(PoLine, PoLine.item_id == Item.id)
            .join(PurchaseOrder, PoLine.po_id == PurchaseOrder.id)
            .where(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.status.in_(("open", "partial")),
            )
            .order_by(Item.sku)
        ).all()
        items_exposed: list[dict[str, object]] = []
        for item, po_number, po_status, qty_ordered in exposed_rows:
            items_exposed.append(
                {
                    "item_id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "criticality": item.criticality,
                    "po_number": po_number,
                    "po_status": po_status,
                    "qty_ordered": float(qty_ordered) if qty_ordered is not None else 0.0,
                }
            )

        return SupplierDetailOut(
            id=sup.id,
            code=sup.code,
            name=sup.name,
            active=sup.active,
            contract_lead_time_days=sup.contract_lead_time_days,
            metrics=metrics_out,
            risk_breakdown=risk_breakdown,
            lead_time_trend=lead_time_trend,
            items_exposed=items_exposed,
        )
    finally:
        session.close()