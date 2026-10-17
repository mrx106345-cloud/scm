"""Logistics agent (Part F3, P3-02): lane delay stats + late-shipment alerts.

Pure computation (``compute_lane_stats``, ``predict_arrival``) is separated from
the DB runner. Delays are deterministic math over ``shipments``; no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean, pstdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, PurchaseOrder, Shipment


@dataclass(frozen=True)
class LaneStats:
    """Delay stats for one carrier/origin/destination lane (days)."""

    mean_delay: float
    std_delay: float


def compute_lane_stats(delays: list[float]) -> LaneStats:
    """Mean and population std of (actual_arrival - eta) per lane."""
    if not delays:
        return LaneStats(mean_delay=0.0, std_delay=0.0)
    return LaneStats(mean_delay=mean(delays), std_delay=pstdev(delays) if len(delays) > 1 else 0.0)


def predict_arrival(eta: datetime, stats: LaneStats) -> datetime:
    """Predicted arrival = eta + lane mean delay (deterministic point estimate)."""
    return eta + timedelta(days=stats.mean_delay)


def run(session: Session, today: datetime | None = None) -> list[tuple[Shipment, str]]:
    """Flag late open shipments; raise ``shipment_late`` supplier_delay alerts.

    Returns ``(shipment, reason)`` pairs: ``past_eta`` or ``past_promised``.
    """
    now = (today or datetime.now(UTC).replace(tzinfo=None)).replace(tzinfo=None)
    shipments = session.scalars(
        select(Shipment).where(Shipment.status.in_(("open", "in_transit", "delayed")))
    ).all()

    # Lane stats from arrived shipments with an actual arrival date.
    lane_delays: dict[tuple[str, str, str], list[float]] = {}
    arrived = session.scalars(
        select(Shipment).where(
            Shipment.actual_arrival.is_not(None),
            Shipment.eta.is_not(None),
        )
    ).all()
    for s in arrived:
        key = (s.carrier, s.origin, s.destination)
        lane_delays.setdefault(key, []).append(
            (s.actual_arrival - s.eta).total_seconds() / 86400.0  # type: ignore[operator]
        )
    lane_stats = {k: compute_lane_stats(v) for k, v in lane_delays.items()}

    flagged: list[tuple[Shipment, str]] = []
    for s in shipments:
        if s.eta is None:
            continue
        reason: str | None = None
        if now > s.eta:
            reason = "past_eta"
        else:
            key = (s.carrier, s.origin, s.destination)
            stats = lane_stats.get(key, LaneStats(0.0, 0.0))
            if _past_promised(session, s, predict_arrival(s.eta, stats)):
                reason = "past_promised"
        if reason is not None:
            flagged.append((s, reason))
            _raise_late_alert(session, s)
    session.flush()
    return flagged


def _past_promised(session: Session, shipment: Shipment, predicted: datetime) -> bool:
    """True when the predicted arrival beats the linked PO's promised date."""
    if shipment.po_id is None:
        return False
    po = session.get(PurchaseOrder, shipment.po_id)
    if po is None or po.promised_date is None:
        return False
    return predicted > po.promised_date


def _raise_late_alert(session: Session, shipment: Shipment) -> None:
    """Upsert one supplier_delay(subtype=shipment_late) alert per PO line item."""
    if shipment.po_id is None:
        return
    po = session.get(PurchaseOrder, shipment.po_id)
    if po is None:
        return
    existing = session.scalar(
        select(Alert).where(
            Alert.dedupe_key == f"shipment_late:{shipment.id}",
            Alert.status.in_(("open", "acknowledged")),
        )
    )
    if existing is not None:
        return
    # Resolve the exposed item through the PO's first line for the alert row.
    from app.db.models import PoLine

    line = session.scalar(
        select(PoLine).where(PoLine.po_id == shipment.po_id).order_by(PoLine.id)
    )
    if line is None:
        return
    session.add(
        Alert(
            item_id=line.item_id,
            site_id=po.site_id,
            supplier_id=po.supplier_id,
            type="supplier_delay",
            severity="high",
            expected_loss=0.0,
            score=0.0,
            status="open",
            dedupe_key=f"shipment_late:{shipment.id}",
        )
    )
