"""Zoho connector tests (P4-07): disabled by default, host policy, mocked write."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.connectors.base import ConnectorError
from app.connectors.zoho import OUTBOUND_WARNING, ZohoConnector

_CONFIG = {"organization_id": "123", "access_token": "tok"}


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict[str, Any] | None = None, **_kwargs: Any) -> None:
        self.payload = payload or {}
        self.calls: list[tuple[str, str]] = []

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("GET", url))
        return _FakeResponse(self.payload)

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("POST", url))
        return _FakeResponse(self.payload)


def test_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", False)
    result = ZohoConnector(_CONFIG).test()
    assert result.ok is False
    assert "disabled" in result.message


def test_write_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", False)
    with pytest.raises(ConnectorError, match="disabled"):
        ZohoConnector(_CONFIG).write(None, {"supplier_name": "A", "sku": "B", "qty": 1})


def test_https_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    result = ZohoConnector(_CONFIG, api_base="http://www.zohoapis.com").test()
    assert result.ok is False
    assert "https" in result.message


def test_host_must_match_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    result = ZohoConnector(_CONFIG, api_base="https://evil.example.com").test()
    assert result.ok is False
    assert "allowlisted" in result.message


def test_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    result = ZohoConnector({"organization_id": "123"}, enabled=True).test()
    assert result.ok is False
    assert "access_token" in result.message


def test_valid_config_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    result = ZohoConnector(_CONFIG, enabled=True).test()
    assert result.ok is True
    assert result.details["outbound"] is True


def test_outbound_warning_is_explicit() -> None:
    assert "network" in OUTBOUND_WARNING


def test_write_requires_payload_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    connector = ZohoConnector(_CONFIG, enabled=True)
    with pytest.raises(ConnectorError, match="supplier, item and quantity"):
        connector.write(None, {"supplier_name": "Acme"})


def test_write_creates_purchase_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    import app.connectors.zoho as zoho_module

    client = _FakeClient({"purchaseorder": {"purchaseorder_number": "PO-9001"}})
    monkeypatch.setattr(zoho_module.httpx, "Client", lambda **_kw: client)

    connector = ZohoConnector(_CONFIG, enabled=True)
    result = connector.write(None, {"supplier_name": "Acme", "sku": "BOLT", "qty": 10})

    assert result.ok is True
    assert result.reference == "PO-9001"
    assert client.calls and client.calls[0][0] == "POST"


def test_write_without_reference_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    import app.connectors.zoho as zoho_module

    monkeypatch.setattr(zoho_module.httpx, "Client", lambda **_kw: _FakeClient({}))
    result = ZohoConnector(_CONFIG, enabled=True).write(
        None, {"supplier_name": "Acme", "sku": "BOLT", "qty": 10}
    )
    assert result.ok is False
    assert "no PO reference" in result.message


def test_run_returns_preview_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_enabled", True)
    import app.connectors.zoho as zoho_module

    payload = {"purchaseorders": [{"purchaseorder_id": "1"}, {"purchaseorder_id": "2"}]}
    monkeypatch.setattr(zoho_module.httpx, "Client", lambda **_kw: _FakeClient(payload))
    result = ZohoConnector(_CONFIG, enabled=True).run(None)
    assert result.status == "ok"
    assert result.metrics["fetched"] == 2
    assert result.imported == 0
