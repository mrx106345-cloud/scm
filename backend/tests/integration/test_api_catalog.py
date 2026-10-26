"""P1-11 tests: alerts/items pagination + pipeline trigger contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import override_auth


def test_catalog_contracts() -> None:
    app = create_app()
    override_auth(app, role="planner")
    client = TestClient(app)
    for path in ("/api/v1/alerts", "/api/v1/items", "/api/v1/pipeline/runs"):
        resp = client.get(path)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"items", "page", "page_size", "total"}
    resp = client.post("/api/v1/pipeline/run")
    assert resp.status_code == 202
    assert resp.json() == {"status": "queued"}
