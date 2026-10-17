"""Supplier agent tests: pure metric math + DB runner (P3-01)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import supplier_agent
from app.db.models import (
    Alert,
    Base,
    Item,
    PoLine,
    PurchaseOrder,
    Receipt,
    Site,
    Supplier,
    SupplierMetrics,
)


def _facts(leads: list[float], late_from: int | None = None) -> list:
    """Build oldest-first receipt facts; receipts at index >= late_from are late."""
    out = []
    for i, lead in enumerate(leads):
        on_time = late_from is None or i < late_from
        out.append(supplier_agent._ReceiptFacts(lead_days=lead, on_time=on_time))
    return out


def test_compute_metrics_drift_and_risk() -> None:
    # prior window (10 receipts): 10d each; recent 5: 20d each -> drift = 1.0
    leads = [10.0] * 10 + [20.0] * 5
    r = supplier_agent.compute_metrics("s1", _facts(leads), dependency_share=0.0)
    assert r.mean_lt_recent == pytest.approx(20.0)
    assert r.mean_lt_prior == pytest.approx(10.0)
    assert r.drift_pct == pytest.approx(1.0)
    assert r.on_time_rate == pytest.approx(1.0)
    assert r.risk_score == 40  # 100*(0.40*1.0 + 0.35*0 + 0.25*0)
    assert r.trend_flag is True  # drift >= 0.25
    assert r.low_data is False


def test_compute_metrics_low_data() -> None:
    r = supplier_agent.compute_metrics("s1", _facts([10.0] * 4), 0.0)
    assert r.low_data is True
    assert r.mean_lt_prior is None
    assert r.drift_pct == 0.0


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_delayed_supplier(session: Session) -> tuple[Supplier, Item]:
    """Supplier with drifting lead times + one open PO for an A item."""
    site = Site(code="S1", name="Plant 1")
    item = Item(
        sku="A-1",
        name="Critical Part",
        uom="EA",
        criticality="A",
        category=None,
        unit_cost=10.0,
        moq=1,
        lot_multiple=1,
    )
    sup = Supplier(code="SUP-1", name="Drift Corp", contract_lead_time_days=10, active=True)
    session.add_all([site, item, sup])
    session.flush()

    # 15 closed POs each with one receipt: first 10 at 10d lead (on time),
    # last 5 at 20d lead (late vs a 10d promise) -> drift 1.0, otr 0.5.
    base = datetime(2025, 9, 1)
    for i in range(15):
        lead = 10 if i < 10 else 20
        order_date = base + timedelta(days=i * 10)
        po = PurchaseOrder(
            po_number=f"PO-{i}",
            supplier_id=sup.id,
            site_id=site.id,
            order_date=order_date,
            promised_date=order_date + timedelta(days=10),
            status="closed",
        )
        session.add(po)
        session.flush()
        line = PoLine(
            po_id=po.id, item_id=item.id, qty_ordered=10, qty_received=10, unit_price=10.0
        )
        session.add(line)
        session.flush()
        session.add(
            Receipt(
                po_line_id=line.id,
                receipt_date=order_date + timedelta(days=lead),
                qty=10.0,
            )
        )

    # One open PO so the item counts as "exposed" for alerting.
    open_po = PurchaseOrder(
        po_number="PO-OPEN",
        supplier_id=sup.id,
        site_id=site.id,
        order_date=datetime(2026, 2, 1),
        promised_date=datetime(2026, 2, 15),
        status="open",
    )
    session.add(open_po)
    session.flush()
    session.add(
        PoLine(po_id=open_po.id, item_id=item.id, qty_ordered=50, qty_received=0, unit_price=10.0)
    )
    session.commit()
    return sup, item


def test_run_upserts_metrics_and_alerts(session: Session) -> None:
    sup, item = _seed_delayed_supplier(session)
    results = supplier_agent.run(session)
    session.commit()

    assert len(results) == 1
    r = results[0]
    assert r.supplier_id == sup.id
    assert r.trend_flag is True
    assert r.risk_score >= 60

    metrics = session.query(SupplierMetrics).all()
    assert len(metrics) == 1
    assert metrics[0].supplier_id == sup.id

    alerts = session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].type == "supplier_delay"
    assert alerts[0].severity == "high"
    assert alerts[0].item_id == item.id
    assert alerts[0].dedupe_key == f"supplier_delay:{item.id}:{alerts[0].site_id}"

    # Second run must dedupe: still one alert, metrics appended.
    supplier_agent.run(session)
    session.commit()
    assert len(session.query(Alert).all()) == 1
    assert len(session.query(SupplierMetrics).all()) == 2

