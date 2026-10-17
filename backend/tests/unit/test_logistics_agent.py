"""Logistics agent tests (P3-02): lane stats + late-shipment alerts."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import logistics_agent
from app.db.models import (
    Alert,
    Base,
    Item,
    PoLine,
    PurchaseOrder,
    Shipment,
    Site,
    Supplier,
)


def _d(days: float) -> datetime:
    return datetime(2026, 1, 1) + timedelta(days=days)


def test_compute_lane_stats_empty_and_single() -> None:
    assert logistics_agent.compute_lane_stats([]) == logistics_agent.LaneStats(0.0, 0.0)
    assert logistics_agent.compute_lane_stats([3.0]) == logistics_agent.LaneStats(3.0, 0.0)


def test_compute_lane_stats_pstdev() -> None:
    s = logistics_agent.compute_lane_stats([0.0, 2.0])  # mean=1, pstdev=1
    assert s.mean_delay == 1.0
    assert s.std_delay == 1.0


def test_predict_arrival_adds_mean_delay() -> None:
    eta = _d(0)
    assert logistics_agent.predict_arrival(eta, logistics_agent.LaneStats(2.0, 0.0)) == _d(2)


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_late_shipment(session: Session) -> Shipment:
    """Shipment whose ETA is in the past -> past_eta flag + alert."""
    site = Site(code="S1", name="Plant 1")
    sup = Supplier(code="SUP-1", name="Late Corp", active=True)
    item = Item(
        sku="A-1", name="Part", uom="EA", criticality="A",
        unit_cost=10.0, moq=1, lot_multiple=1,
    )
    session.add_all([site, sup, item])
    session.flush()
    po = PurchaseOrder(
        po_number="PO-1", supplier_id=sup.id, site_id=site.id,
        order_date=_d(-10), promised_date=_d(20), status="open",
    )
    session.add(po)
    session.flush()
    session.add(
        PoLine(po_id=po.id, item_id=item.id, qty_ordered=10, qty_received=0, unit_price=10.0)
    )
    session.flush()
    return Shipment(
        po_id=po.id, reference="REF-1", carrier="C1", origin="O", destination="D",
        ship_date=_d(-5), eta=_d(-1), status="in_transit",
    )


def test_run_flags_past_eta_and_raises_alert(session: Session) -> None:
    s = _seed_late_shipment(session)
    session.add(s)
    session.commit()

    flagged = logistics_agent.run(session, today=_d(0))
    session.commit()

    assert len(flagged) == 1
    assert flagged[0][1] == "past_eta"

    alerts = session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].type == "supplier_delay"
    assert alerts[0].dedupe_key == f"shipment_late:{s.id}"
    assert alerts[0].severity == "high"

    # Second run dedupes: still one alert.
    logistics_agent.run(session, today=_d(0))
    session.commit()
    assert len(session.query(Alert).all()) == 1
