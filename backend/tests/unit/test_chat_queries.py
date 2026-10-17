"""Unit tests for the fixed read-only chat query functions (Part H4).

Sets up an in-memory SQLite session with a couple of item / supplier / alert
rows and asserts the functions return the expected fact shapes and values.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.chat.queries import (
    explain_alert,
    item_status,
    list_alerts,
    savings_report,
    supplier_summary,
)
from app.db.models import Alert, Base, Item, Supplier  # noqa: E402


@pytest.fixture()
def session() -> Session:
    """Fresh in-memory SQLite session with a couple of rows for the tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    s = maker()

    item = Item(
        sku="HB-M8",
        name="Hex Bolt M8",
        uom="EA",
        criticality="B",
        category="fastener",
        unit_cost=1.20,
        moq=10,
        lot_multiple=5,
    )
    s.add(item)
    supplier = Supplier(
        code="SUP-01",
        name="Alpha Steels",
        contract_lead_time_days=14,
        active=True,
    )
    s.add(supplier)
    s.flush()  # materialise ids so alert.item_id resolves
    alert = Alert(
        item_id=item.id,
        site_id="site-a",
        supplier_id=supplier.id,
        type="supplier_delay",
        severity="high",
        expected_loss=350.0,
        score=62.5,
        status="open",
        dedupe_key="delay-alpha-77",
    )
    s.add(alert)
    alert.created_at = datetime(2025, 6, 1)
    s.commit()
    return s


def test_item_status_returns_master_fields(session: Session) -> None:
    result = item_status(
        Item(
            sku="HB-M8",
            name="Hex Bolt M8",
            uom="EA",
            criticality="B",
            category="fastener",
            unit_cost=1.20,
            moq=10,
            lot_multiple=5,
        ),
        session,
    )
    assert result["item"]["sku"] == "HB-M8"
    assert result["item"]["name"] == "Hex Bolt M8"
    assert result["item"]["criticality"] == "B"
    assert abs(float(result["item"]["unit_cost"]) - 1.20) < 0.001


def test_list_alerts_filters_by_severity(session: Session) -> None:
    result = list_alerts("high", None, session)
    assert result["total"] == 1
    assert result["alerts"][0]["severity"] == "high"
    assert result["alerts"][0]["item_sku"] == "HB-M8"


def test_list_alerts_filters_by_supplier(session: Session) -> None:
    result = list_alerts(None, "Alpha Steels", session)
    assert result["total"] == 1


def test_list_alerts_sorts_newest_first(session: Session) -> None:
    older = Alert(
        item_id="x",
        site_id="site-a",
        supplier_id="y",
        type="dead_stock",
        severity="critical",
        expected_loss=10.0,
        score=10.0,
        status="open",
        dedupe_key="old",
    )
    newer = Alert(
        item_id="x",
        site_id="site-a",
        supplier_id="y",
        type="excess",
        severity="medium",
        expected_loss=5.0,
        score=5.0,
        status="open",
        dedupe_key="new",
    )
    older.created_at = datetime(2026, 1, 1)
    newer.created_at = datetime(2026, 1, 2)
    session.add_all([older, newer])
    session.commit()
    result = list_alerts(None, None, session)
    assert result["total"] == 3
    assert result["alerts"][0]["severity"] == "medium"


def test_supplier_summary_returns_drift_and_delays(session: Session) -> None:
    result = supplier_summary(
        Supplier(
            code="SUP-01",
            name="Alpha Steels",
            contract_lead_time_days=14,
            active=True,
        ),
        session,
    )
    assert result["supplier"]["name"] == "Alpha Steels"
    assert result["supplier"]["contract_lead_time_days"] == 14
    assert result["lead_time_drift_pct"] == 0.0


def test_forecast_bests_naive(session: Session) -> None:
    from app.chat.queries import forecast  # noqa: F401

    series = [10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0, 14.5, 16.0]
    item = Item(
        sku="X",
        name="Test",
        uom="EA",
        criticality="A",
        category=None,
        unit_cost=None,
        moq=1,
        lot_multiple=1,
    )
    fc = forecast(item, series, session)
    assert fc["method"] in (
        "naive",
        "moving_average_8",
        "moving_average_13",
        "seasonal_naive",
        "croston_sba",
    )
    assert fc["wape"] >= 0.0
    assert len(fc["forecast"]) == 4
    assert all(isinstance(v, float) for v in fc["forecast"])


def test_explain_alert_returns_facts(session: Session) -> None:
    result = explain_alert("does-not-exist", session)
    assert result["alert"] is None
    assert result["facts"] == {}


def test_savings_report_returns_period(session: Session) -> None:
    result = savings_report("last_quarter", session)
    assert result["period"] == "last_quarter"
    assert result["estimated_savings"] == 0.0
