"""Supplier agent (Part F3, P3-01): metrics + supplier_delay alerts.

Pure computation is factored into ``compute_metrics`` (no DB, no clock); the
agent runner reads receipts, upserts a ``supplier_metrics`` row and raises
deduped ``supplier_delay`` alerts when ``trend_flag`` or ``risk_score >= 60``.
Numbers come from deterministic code only; the LLM never touches this path.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.alerting import supplier_risk, supplier_trend_flag
from app.db.models import (
    Alert,
    Item,
    PoLine,
    PurchaseOrder,
    Receipt,
    Supplier,
    SupplierMetrics,
)

MIN_RECEIPTS_FULL = 8  # below this: partial metrics + low_data flag
RISK_ALERT_THRESHOLD = 60


@dataclass(frozen=True)
class SupplierMetricResult:
    """Computed metrics for one supplier (spec Part F3)."""

    supplier_id: str
    mean_lt_recent: float | None
    mean_lt_prior: float | None
    drift_pct: float
    on_time_rate: float
    dependency_share: float
    risk_score: int
    trend_flag: bool
    low_data: bool


@dataclass(frozen=True)
class _ReceiptFacts:
    """Per-receipt lead-time and punctuality facts for one supplier."""

    lead_days: float
    on_time: bool


def compute_metrics(
    supplier_id: str,
    receipts: list[_ReceiptFacts],
    dependency_share: float,
    grace_days: int = 1,
) -> SupplierMetricResult:
    """Compute drift/on-time/risk from receipt facts (spec Part F3).

    ``receipts`` must be ordered oldest first. With fewer than 8 receipts the
    result is marked ``low_data`` and risk uses whatever parts are available.
    """
    n = len(receipts)
    leads = [r.lead_days for r in receipts]
    low_data = n < MIN_RECEIPTS_FULL
    recent = mean(leads[-5:]) if n else None
    prior_window = leads[-15:-5]
    prior = mean(prior_window) if len(prior_window) >= 5 else None
    if recent is not None and prior is not None and prior != 0.0:
        drift = (recent - prior) / prior
    else:
        drift = 0.0
    last10 = receipts[-10:]
    otr = mean(1.0 if r.on_time else 0.0 for r in last10) if last10 else 1.0
    risk = supplier_risk(drift, otr, dependency_share)
    trend = supplier_trend_flag(leads, drift)
    return SupplierMetricResult(
        supplier_id=supplier_id,
        mean_lt_recent=recent,
        mean_lt_prior=prior,
        drift_pct=drift,
        on_time_rate=otr,
        dependency_share=dependency_share,
        risk_score=risk,
        trend_flag=trend,
        low_data=low_data,
    )


def _load_receipt_facts(session: Session, supplier_id: str) -> list[_ReceiptFacts]:
    """Receipts for one supplier, ordered oldest first."""
    rows = session.execute(
        select(Receipt.receipt_date, PurchaseOrder.order_date, PurchaseOrder.promised_date)
        .join(PoLine, Receipt.po_line_id == PoLine.id)
        .join(PurchaseOrder, PoLine.po_id == PurchaseOrder.id)
        .where(PurchaseOrder.supplier_id == supplier_id)
        .order_by(Receipt.receipt_date)
    ).all()
    facts: list[_ReceiptFacts] = []
    for receipt_date, order_date, promised_date in rows:
        lead = (receipt_date - order_date).total_seconds() / 86400.0
        on_time = promised_date is not None and receipt_date <= promised_date + timedelta(days=1)
        facts.append(_ReceiptFacts(lead_days=lead, on_time=on_time))
    return facts


def _dependency_share(session: Session, supplier_id: str) -> float:
    """For A items: avg over A items of this supplier's 12-month qty share."""
    a_items = session.scalars(select(Item).where(Item.criticality == "A")).all()
    if not a_items:
        return 0.0
    shares: list[float] = []
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=365)
    for item in a_items:
        rows = session.execute(
            select(PurchaseOrder.supplier_id, Receipt.qty)
            .join(PoLine, Receipt.po_line_id == PoLine.id)
            .join(PurchaseOrder, PoLine.po_id == PurchaseOrder.id)
            .where(PoLine.item_id == item.id, Receipt.receipt_date >= cutoff)
        ).all()
        total = sum(float(q) for _, q in rows)
        if total <= 0:
            continue
        own = sum(float(q) for sid, q in rows if sid == supplier_id)
        shares.append(own / total)
    return mean(shares) if shares else 0.0


def run(session: Session, grace_days: int = 1) -> list[SupplierMetricResult]:
    """Compute metrics for every active supplier; raise deduped delay alerts."""
    suppliers = session.scalars(select(Supplier).where(Supplier.active)).all()
    results: list[SupplierMetricResult] = []
    for sup in suppliers:
        facts = _load_receipt_facts(session, sup.id)
        dep = _dependency_share(session, sup.id)
        result = compute_metrics(sup.id, facts, dep, grace_days)
        results.append(result)
        session.add(
            SupplierMetrics(
                supplier_id=sup.id,
                mean_lt_recent=result.mean_lt_recent,
                mean_lt_prior=result.mean_lt_prior,
                drift_pct=result.drift_pct,
                on_time_rate=result.on_time_rate,
                dependency_share=result.dependency_share,
                risk_score=result.risk_score,
                trend_flag=result.trend_flag,
                details=json.dumps({k: v for k, v in asdict(result).items() if k != "supplier_id"}),
            )
        )
        if result.trend_flag or result.risk_score >= RISK_ALERT_THRESHOLD:
            _raise_supplier_delay_alert(session, sup, result)
    session.flush()
    return results


def _raise_supplier_delay_alert(
    session: Session, supplier: Supplier, result: SupplierMetricResult
) -> None:
    """Upsert one supplier_delay alert per exposed (A/B, open PO) item."""
    exposed = session.execute(
        select(Item, PurchaseOrder.site_id)
        .join(PoLine, PoLine.item_id == Item.id)
        .join(PurchaseOrder, PoLine.po_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.supplier_id == supplier.id,
            PurchaseOrder.status.in_(("open", "partial")),
            Item.criticality.in_(("A", "B")),
        )
    ).all()
    seen: set[tuple[str, str]] = set()
    for item, site_id in exposed:
        key = (item.id, site_id)
        if key in seen:
            continue
        seen.add(key)
        dedupe_key = f"supplier_delay:{item.id}:{site_id}"
        existing = session.scalar(
            select(Alert).where(
                Alert.dedupe_key == dedupe_key,
                Alert.status.in_(("open", "acknowledged")),
            )
        )
        score = float(result.risk_score)
        if existing is None:
            session.add(
                Alert(
                    item_id=item.id,
                    site_id=site_id,
                    supplier_id=supplier.id,
                    type="supplier_delay",
                    severity="high" if result.risk_score >= 60 else "medium",
                    expected_loss=0.0,
                    score=score,
                    status="open",
                    dedupe_key=dedupe_key,
                )
            )
        else:
            existing.score = score
            # Re-escalate severity when the risk moves across the 60 threshold;
            # previously severity froze at the value from the first run.
            existing.severity = "high" if result.risk_score >= 60 else "medium"
