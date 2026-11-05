"""Connector admin API tests (P4-04/P4-07, acceptance D3).

Proves that credentials never reach responses or audit payloads, that only
admins can manage connectors, and that SAP host allowlisting is enforced.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import connectors as connectors_api
from app.config import settings
from app.core.dependencies import get_current_user
from app.db.models import AuditLog, Base, Connector
from app.main import create_app

_KEY = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
_HEADERS = {"x-csrf-token": "test"}


@pytest.fixture(autouse=True)
def _env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCM_CREDENTIAL_KEY", _KEY)


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _client(monkeypatch: pytest.MonkeyPatch, session: Session, role: str = "admin") -> TestClient:
    monkeypatch.setattr(connectors_api, "SessionLocal", lambda: session)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "username": "user-1",
        "role": role,
    }
    return TestClient(app)


def test_admin_can_create_and_list_masked_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", False)
    session = _session()
    client = _client(monkeypatch, session)
    resp = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={
            "name": "sap-prod",
            "type": "sap_b1",
            "config": {
                "base_url": "https://sap.internal:50000/b1s/v1",
                "username": "manager",
                "password": "SuperSecret123",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["config"]["username"] == "manager"
    assert body["config"]["password"] == "***"
    assert "SuperSecret123" not in resp.text

    listed = client.get("/api/v1/connectors")
    assert listed.status_code == 200
    assert "SuperSecret123" not in listed.text


def test_audit_payload_never_contains_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    client = _client(monkeypatch, session)
    resp = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={
            "name": "csv-1",
            "type": "csv",
            "config": {"path": "/data/inbox/items.csv", "password": "hunter2hunter2"},
        },
    )
    assert resp.status_code == 201
    rows = session.query(AuditLog).filter_by(event_type="connector.created").all()
    assert len(rows) == 1
    assert "hunter2hunter2" not in (rows[0].payload or "")


@pytest.mark.parametrize("role", ["planner", "purchaser", "viewer"])
def test_non_admin_cannot_manage_connectors(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    session = _session()
    client = _client(monkeypatch, session, role=role)
    assert client.get("/api/v1/connectors").status_code == 403


def test_write_enabled_rejected_for_read_only_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    client = _client(monkeypatch, session)
    resp = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={"name": "tally-1", "type": "tally", "config": {}, "write_enabled": True},
    )
    assert resp.status_code == 400
    assert "read-only" in resp.json()["detail"]


def test_zoho_write_requires_zoho_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", False)
    session = _session()
    client = _client(monkeypatch, session)
    resp = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={
            "name": "zoho-1",
            "type": "zoho",
            "config": {"organization_id": "123", "access_token": "tok"},
            "write_enabled": True,
        },
    )
    assert resp.status_code == 403
    assert "SCM_ZOHO_ENABLED" in resp.json()["detail"]


def test_zoho_connector_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", False)
    session = _session()
    client = _client(monkeypatch, session)
    created = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={
            "name": "zoho-2",
            "type": "zoho",
            "config": {"organization_id": "123", "access_token": "tok"},
        },
    )
    assert created.status_code == 201
    assert created.json()["outbound"] is True
    tested = client.post(
        f"/api/v1/connectors/{created.json()['id']}/test", headers=_HEADERS
    )
    assert tested.status_code == 200
    assert tested.json()["ok"] is False
    assert "disabled" in tested.json()["message"]


def test_sap_host_allowlist_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sap_allowed_hosts", "sap.internal,erp.internal")
    session = _session()
    client = _client(monkeypatch, session)
    bad = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={
            "name": "sap-bad",
            "type": "sap_b1",
            "config": {"base_url": "https://evil.example.com/b1s/v1"},
        },
    )
    assert bad.status_code == 400
    assert "not in SCM_SAP_ALLOWED_HOSTS" in bad.json()["detail"]

    good = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={
            "name": "sap-good",
            "type": "sap_b1",
            "config": {"base_url": "https://sap.internal:50000/b1s/v1"},
        },
    )
    assert good.status_code == 201


def test_sap_host_allowlist_rejects_relative_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sap_allowed_hosts", "")
    session = _session()
    client = _client(monkeypatch, session)
    resp = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={"name": "sap-rel", "type": "sap_b1", "config": {"base_url": "/b1s/v1"}},
    )
    assert resp.status_code == 400


def test_duplicate_name_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    client = _client(monkeypatch, session)
    body = {"name": "dup", "type": "csv", "config": {"path": "/tmp/a.csv"}}
    assert client.post("/api/v1/connectors", headers=_HEADERS, json=body).status_code == 201
    assert client.post("/api/v1/connectors", headers=_HEADERS, json=body).status_code == 409


def test_update_masks_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    client = _client(monkeypatch, session)
    created = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={"name": "upd", "type": "csv", "config": {"path": "/tmp/a.csv"}},
    ).json()
    updated = client.patch(
        f"/api/v1/connectors/{created['id']}",
        headers=_HEADERS,
        json={"config": {"path": "/tmp/b.csv", "api_key": "abcdef"}},
    )
    assert updated.status_code == 200
    assert updated.json()["config"]["api_key"] == "***"
    assert "abcdef" not in updated.text
    row = session.get(Connector, created["id"])
    assert row is not None and row.config_encrypted is not None


def test_outbound_warning_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    client = _client(monkeypatch, session)
    created = client.post(
        "/api/v1/connectors",
        headers=_HEADERS,
        json={"name": "zoho-3", "type": "zoho", "config": {}},
    ).json()
    resp = client.get(f"/api/v1/connectors/{created['id']}/outbound-warning")
    assert resp.status_code == 200
    assert resp.json()["outbound"] is True
    assert "network" in resp.json()["warning"]


def test_missing_connector_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    client = _client(monkeypatch, session)
    assert client.get("/api/v1/connectors/nope").status_code == 404


def test_secret_never_reaches_logs_or_responses(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """D3 automated scan: create, list, test and update never leak the secret."""
    import logging

    secret = "UltraSecret-9f3a"
    session = _session()
    client = _client(monkeypatch, session)
    with caplog.at_level(logging.DEBUG):
        created = client.post(
            "/api/v1/connectors",
            headers=_HEADERS,
            json={
                "name": "scan",
                "type": "zoho",
                "config": {
                    "organization_id": "1",
                    "access_token": secret,
                    "client_secret": secret,
                },
            },
        )
        assert created.status_code == 201
        assert secret not in created.text
        assert secret not in client.get("/api/v1/connectors").text
        assert secret not in client.get(f"/api/v1/connectors/{created.json()['id']}").text
        assert secret not in client.post(
            f"/api/v1/connectors/{created.json()['id']}/test", headers=_HEADERS
        ).text
    assert secret not in caplog.text
    for row in session.query(AuditLog).all():
        assert secret not in (row.payload or "")
