"""Recommendation agent tests (P3-03): draft POs + supplier message templates."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import recommendation_agent
from app.db.models import (
    Alert,
    Base,
    Item,
    PoLine,
    PurchaseOrder,
    Recommendation,
    Site,
    Supplier,
)


def _d(days: float) -> datetime:
    return datetime(2026, 1, 1) + timedelta(days=days)


def test_compute_order_qty_fallback_to_moq() -> None:
    item = Item(moq=100.0, lot_multiple=50.0, unit_cost=10.0)
    # No inventory params -> fall back to moq rounded up to lot multiple.
    assert recommendation_agent.compute_order_qty(item) == 100.0
    item2 = Item(moq=120.0, lot_multiple=50.0, unit_cost=10.0)
    assert recommendation_agent.compute_order_qty(item2) == 150.0


def test_compute_order_qty_spec_formula() -> None:
    item = Item(moq=100.0, lot_multiple=50.0, unit_cost=10.0)
    # Q=600, ROP=374.2, A=130 -> max(600, 844.2)=844.2 -> lot 50 -> 850.
    qty = recommendation_agent.compute_order_qty(item, q=600.0, rop=374.2, available=130.0)
    assert qty == 850.0


def test_draft_supplier_message_fills_placeholders() -> None:
    msg = recommendation_agent.draft_supplier_message(
        supplier_name="Acme Steels",
        po_number="PO-100",
        item_sku="BOLT-M8",
        qty=850.0,
        promised_date=_d(15),
    )
    assert "PO-100" in msg.subject and "BOLT-M8" in msg.subject
    for token in ("Acme Steels", "PO-100", "BOLT-M8", "850", "2026-01-16", "confirm"):
        assert token.lower() in msg.body.lower()


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(session: Session, alert_type: str) -> str:
    site = Site(code="S1", name="Plant 1")
    sup = Supplier(code="SUP-1", name="Acme Steels", active=True)
    item = Item(
        sku="BOLT-M8",
        name="Hex Bolt",
        uom="EA",
        criticality="A",
        unit_cost=250.0,
        moq=100.0,
        lot_multiple=50.0,
        stockout_cost=1000.0,
    )
    session.add_all([site, sup, item])
    session.flush()
    po = PurchaseOrder(
        po_number="PO-100",
        supplier_id=sup.id,
        site_id=site.id,
        order_date=_d(-10),
        promised_date=_d(15),
        status="open",
    )
    session.add(po)
    session.flush()
    session.add(
        PoLine(
            po_id=po.id,
            item_id=item.id,
            qty_ordered=850.0,
            qty_received=0.0,
            unit_price=250.0,
        )
    )
    session.flush()
    session.add(
        Alert(
            item_id=item.id,
            site_id=site.id,
            supplier_id=sup.id,
            type=alert_type,
            severity="high",
            expected_loss=240000.0,
            score=80.0,
            status="open",
            dedupe_key=f"alert:{alert_type}:1",
        )
    )
    session.commit()
    return item.id


def test_create_recommendations_stockout_risk(session: Session) -> None:
    _seed(session, "stockout_risk")
    recs = recommendation_agent.create_recommendations(session)
    session.commit()
    assert len(recs) == 1
    rec = recs[0]
    assert rec.action_type == "create_draft_po"
    assert rec.status == "pending"
    assert rec.est_benefit == 240000.0
    import json

    payload = json.loads(rec.payload or "{}")
    assert payload["qty"] == 100.0  # moq fallback, lot 50 -> 100

    recs2 = recommendation_agent.create_recommendations(session)
    session.commit()
    assert recs2 == []  # idempotent: no duplicates on second run
    assert len(session.query(Recommendation).all()) == 1


def test_create_recommendations_supplier_delay(session: Session) -> None:
    _seed(session, "supplier_delay")
    recs = recommendation_agent.create_recommendations(session)
    session.commit()
    assert len(recs) == 1
    rec = recs[0]
    assert rec.action_type == "draft_supplier_message"
    payload = json.loads(rec.payload or "{}")
    assert "Acme Steels" in payload["message_text"]
    assert "PO-100" in payload["message_text"]
    assert rec.est_benefit == 240000.0
