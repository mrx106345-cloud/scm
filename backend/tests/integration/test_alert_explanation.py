"""Integration test: GET /api/v1/alerts/{id}/explanation (Part M item 4).

Badge disclosure: source is `llm` or `template` per H3 retry/validate;
facts echo the same numbers shown in text (validator-enforced upstream).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.catalog as catalog_mod
from app.db.models import Alert, Base, Item, Supplier
from app.main import create_app


@pytest.fixture()
def seeded_client() -> tuple[TestClient, str]:
    """App whose catalog session factory reads one seeded in-memory alert."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    session = maker()
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
    session.add(item)
    sup = Supplier(code="SUP-01", name="Alpha Steels", contract_lead_time_days=14, active=True)
    session.add(sup)
    session.flush()
    session.add(
        Alert(
            item_id=item.id,
            site_id="site-a",
            supplier_id=sup.id,
            type="supplier_delay",
            severity="high",
            expected_loss=350.0,
            score=62.5,
            status="open",
            dedupe_key="delay-alpha-77",
        )
    )
    session.commit()
    alert_id = session.query(Alert).first().id

    real_local = catalog_mod.SessionLocal
    catalog_mod.SessionLocal = lambda: maker()  # noqa: E731
    try:
        yield TestClient(create_app()), alert_id
    finally:
        catalog_mod.SessionLocal = real_local


def test_explanation_discloses_template_source(seeded_client: tuple[TestClient, str]) -> None:
    client, alert_id = seeded_client
    resp = client.get(f"/api/v1/alerts/{alert_id}/explanation")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {
        "alert_id",
        "summary",
        "why",
        "suggested_action",
        "source",
        "validator",
        "facts",
    }
    # Offline deterministic path forces template (validator rejects canned).
    assert body["source"] == "template"
    # Badge text only draws from computed facts: name + lead days + loss.
    assert "Hex Bolt M8" in body["summary"] or "Hex Bolt M8" in body["why"]
    assert "14" in body["why"]
    assert "350.00" in body["suggested_action"] or "350.00" in body["why"]
    # Facts echo the numbers shown.
    assert body["facts"]["item_name"] == "Hex Bolt M8"
    assert body["facts"]["expected_loss"] == "350.00"


def test_explanation_404_for_missing(seeded_client: tuple[TestClient, str]) -> None:
    client, _ = seeded_client
    resp = client.get("/api/v1/alerts/does-not-exist/explanation")
    assert resp.status_code == 404
