"""P1-11 tests: dashboard contract per api-spec A3."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_dashboard_summary_contract() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "as_of",
        "alerts",
        "expected_loss_at_risk",
        "data_quality",
        "pending_recommendations",
    }
    assert body["expected_loss_at_risk"]["label"] == "estimate"
