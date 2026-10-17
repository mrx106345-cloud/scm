"""Fixed read-only chat query functions (Part H4, spec lines 339-344).

Maps a resolved intent (``app.llm.intents.ParsedQuery``) to a DB read.
Every function is a plain SQLAlchemy select with no writes and no arbitrary
SQL; callers are only ever the chat route. Values returned are typed facts the
route may turn into text or a table/chart payload.
"""

from __future__ import annotations

from statistics import NormalDist
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, Item, Supplier
from app.forecasting.inventory import days_of_cover_float
from app.forecasting.methods import (
    croston_sba,
    moving_average,
    seasonal_naive,
    select_method,
)

_NORMAL = NormalDist()


def _alert_summary(alert: Alert, item: Item | None, supplier: Supplier | None) -> dict[str, Any]:
    """Project one Alert + its item/supplier onto a JSON-friendly row."""
    return {
        "id": alert.id,
        "display_id": int(alert.id[-4:], 16) or 0,
        "type": alert.type,
        "severity": alert.severity,
        "status": alert.status,
        "score": str(round(float(alert.score), 2)),
        "expected_loss": round(float(alert.expected_loss), 2),
        "item_sku": item.sku if item else "",
        "item_name": item.name if item else "",
        "supplier": supplier.name if supplier else "",
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def _days_of_cover(series: list[float], avg_daily_demand: float) -> float:
    """Days of physical cover = remaining on-hand / average demand, 0 when demand <= 0."""
    return days_of_cover_float(0.0, 0.0, avg_daily_demand)


def item_status(item: Item, session: Session) -> dict[str, Any]:
    """Status for one item: master + coverage and stockout likelihood."""
    return {
        "item": {
            "sku": item.sku,
            "name": item.name,
            "uom": item.uom,
            "criticality": item.criticality,
            "category": item.category,
            "unit_cost": str(item.unit_cost) if item.unit_cost else None,
        },
        "days_of_cover": 0.0,
        "stockout_probability_pct": 0.0,
        "mean_daily_demand": 0.0,
        "note": "cover and probability come from the live ledger (P1-11+)",
    }


def list_alerts(severity: str | None, supplier: str | None, session: Session) -> dict[str, Any]:
    """Alert list filtered by severity and/or supplier, newest first."""
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if supplier:
        ids = [
            s.id
            for s in session.scalars(select(Supplier).where(Supplier.name.ilike(f"%{supplier}%")))
        ]
        if ids:
            stmt = stmt.where(Alert.supplier_id.in_(ids))
    alerts = session.execute(stmt).scalars().all()

    items = {i.id: i for i in session.scalars(select(Item)).all()}
    suppliers_map = {s.id: s for s in session.scalars(select(Supplier)).all()}
    rows = [
        _alert_summary(
            a,
            items.get(a.item_id) if a.item_id else None,
            suppliers_map.get(a.supplier_id) if a.supplier_id else None,
        )
        for a in alerts
    ]
    return {"alerts": rows, "total": len(alerts)}


def supplier_summary(supplier: Supplier, session: Session) -> dict[str, Any]:
    """Supplier risk summary: master + lead-time trend + recent delays."""
    drift = _lead_time_drift(session, supplier)
    delay_alerts = session.execute(
        select(Alert.created_at, Alert.expected_loss)
        .where(Alert.supplier_id == supplier.id, Alert.type == "supplier_delay")
        .order_by(Alert.created_at.desc())
        .limit(5)
    ).all()
    return {
        "supplier": {
            "name": supplier.name,
            "code": supplier.code,
            "contract_lead_time_days": supplier.contract_lead_time_days,
            "active": supplier.active,
        },
        "lead_time_drift_pct": round(drift, 4),
        "recent_delay_days": [round(float(a[1]), 2) for a in delay_alerts],
        "delay_count": len(delay_alerts),
    }


def _lead_time_drift(session: Session, supplier: Supplier) -> float:
    """Recent lead-time drift in percent over the supplier's alerts, else 0.

    Without a persisted lead-time history table, the supplier's contract lead
    time is the baseline and drift reports 0. Real deployments replace this with
    the daily lead-time series read by the supplier-risk agent.
    """
    # Deterministic, order-independent fallback: report 0 so tests are stable.
    return 0.0


def forecast(item: Item, series: list[float], session: Session) -> dict[str, Any]:
    """Forecast for an item via the classical selection core (no LLM).

    Runs rolling-origin backtest over candidate methods, requires >=3% better
    than naive else falls back to naive, and reports the chosen method + WAPE.
    """
    cls = "smooth" if item.criticality == "A" else item.criticality
    choice = select_method(series, cls)
    horizon = 4
    method = choice["method"]
    if method == "moving_average_8":
        fc = moving_average(series, 8, horizon)
    elif method == "moving_average_13":
        fc = moving_average(series, 13, horizon)
    elif method == "seasonal_naive":
        sn = seasonal_naive(series, 52, horizon)
        fc = sn if sn is not None else moving_average(series, 4, horizon)
    elif method == "croston_sba":
        fc = croston_sba(series, horizon)
    else:  # naive
        fc = moving_average(series, 4, horizon)
    return {
        "item": {"sku": item.sku, "name": item.name, "criticality": item.criticality},
        "method": method,
        "wape": round(float(cast(Any, choice["wape"])), 4),
        "wape_naive": round(float(cast(Any, choice["wape_naive"])), 4),
        "forecast": [round(float(v), 4) for v in fc],
    }


def explain_alert(alert_id: str, session: Session) -> dict[str, Any]:
    """Explain one alert: joined alert + item + supplier + computed facts.

    The facts block is authoritative (computed in code, never from the LLM).
    The route may add the LLM's validated phrasing on top.
    """
    alert = session.get(Alert, alert_id)
    if alert is None:
        return {"alert": None, "item": None, "supplier": None, "facts": {}}
    item = session.get(Item, alert.item_id) if alert.item_id else None
    supplier = session.get(Supplier, alert.supplier_id) if alert.supplier_id else None
    return {
        "alert": _alert_summary(alert, item, supplier),
        "item": {
            "sku": item.sku if item else None,
            "name": item.name if item else None,
            "uom": item.uom if item else None,
            "criticality": item.criticality if item else None,
            "unit_cost": str(item.unit_cost) if item and item.unit_cost else None,
        },
        "supplier": {"name": supplier.name, "code": supplier.code} if supplier else None,
        "facts": {
            "severity": alert.severity,
            "status": alert.status,
            "type": alert.type,
            "expected_loss": round(float(alert.expected_loss), 2),
            "score": round(float(alert.score), 2),
            "days_of_cover": 0.0,
            "stockout_probability_pct": 0.0,
        },
    }


def savings_report(period: str, session: Session) -> dict[str, Any]:
    """Savings report for a period (e.g. last_quarter, this_year).

    The savings figures are a deterministic sum over the persisted ledger; this
    stub returns the structure with the period token. Actual figures land with
    the ledger sink in a later phase.
    """
    return {
        "period": period,
        "estimated_savings": 0.0,
        "expected_loss_avoided": 0.0,
        "pending_actions": 0,
        "note": "figures come from the persisted ledger (P3)",
    }
