"""P1-11 tests: dashboard contract per api-spec A3.

The summary reads the live ledger: severity counts come from
open/acknowledged alerts, expected loss is their sum, and
pending_recommendations counts only status='pending'. This test pins those
numbers against a seeded in-memory DB (monkeypatched module SessionLocal).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.routes as routes_mod
from app.db.models import Alert, Base, Item, Recommendation, Site
from app.main import create_app
from tests.helpers import override_auth


@pytest.fixture()
def seeded_client() -> TestClient:
    """App whose routes session factory reads one seeded in-memory ledger."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    site = Site(id="site-a", code="P1", name="Plant 1")
    item = Item(sku="HB-M8", name="Hex Bolt M8", uom="EA", criticality="A")
    session.add_all([site, item])
    session.flush()

    def al(**kw: object) -> Alert:
        """One alert on the seeded item/site with explicit fields."""
        return Alert(item_id=item.id, site_id=site.id, **kw)  # type: ignore[arg-type]

    session.add_all(
        [
            al(
                type="stockout_risk",
                severity="critical",
                expected_loss=1200.50,
                score=300.0,
                status="open",
                dedupe_key="so-1",
            ),
            al(
                type="supplier_delay",
                severity="high",
                expected_loss=300.00,
                score=60.0,
                status="acknowledged",
                dedupe_key="sd-1",
            ),
            al(
                type="supplier_delay",
                severity="medium",
                expected_loss=50.25,
                score=20.0,
                status="open",
                dedupe_key="sd-2",
            ),
            # Resolved alerts are excluded from the at-risk numbers.
            al(
                type="stockout_risk",
                severity="critical",
                expected_loss=99999.0,
                score=99999.0,
                status="resolved",
                dedupe_key="so-2",
            ),
        ]
    )
    session.flush()
    rec1 = session.query(Alert).filter(Alert.dedupe_key == "so-1").first()
    session.add_all(
        [
            Recommendation(
                display_id=1,
                alert_id=rec1.id,
                action_type="create_draft_po",
                status="pending",
            ),
            Recommendation(
                display_id=2,
                alert_id=rec1.id,
                action_type="create_draft_po",
                status="approved",
            ),
        ]
    )
    session.commit()

    real_local = routes_mod.SessionLocal
    routes_mod.SessionLocal = lambda: sessionmaker(bind=engine)()  # noqa: E731
    app = create_app()
    override_auth(app, role="viewer")
    try:
        yield TestClient(app)
    finally:
        routes_mod.SessionLocal = real_local


def test_dashboard_summary_contract(seeded_client: TestClient) -> None:
    """Shape per A3 plus real numbers computed from the seeded ledger."""
    resp = seeded_client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {
        "as_of",
        "alerts",
        "expected_loss_at_risk",
        "data_quality",
        "pending_recommendations",
    }
    assert body["expected_loss_at_risk"]["label"] == "estimate"
    assert set(body["alerts"]) == {"critical", "high", "medium"}
    assert body["alerts"]["critical"] == 1  # the resolved critical is excluded
    assert body["alerts"]["high"] == 1
    assert body["alerts"]["medium"] == 1
    # 1200.50 + 300.00 + 50.25, money as a 2dp decimal string.
    assert body["expected_loss_at_risk"]["amount"] == "1550.75"
    assert body["pending_recommendations"] == 1
