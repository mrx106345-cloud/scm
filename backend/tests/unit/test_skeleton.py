"""P1-01 skeleton tests: config loads, app boots, inventory stub behaves."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.agents.inventory_math import days_of_cover
from app.config import settings
from app.main import create_app


def test_settings_defaults() -> None:
    assert settings.target_cover_days == 30
    assert settings.currency == "INR"


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_days_of_cover_basic() -> None:
    assert days_of_cover(Decimal("400"), Decimal("20"), Decimal("20")) == Decimal("19")


def test_days_of_cover_zero_demand() -> None:
    assert days_of_cover(Decimal("100"), Decimal("0"), Decimal("0")) == Decimal("0")
