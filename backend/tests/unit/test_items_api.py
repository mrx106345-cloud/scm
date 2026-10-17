"""Item detail API tests (P3-07, spec item page).

Covers item detail with master parameters, forecast, alert history,
open POs, plus role enforcement on the routes.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import items as items_api
from app.core.dependencies import get_current_user
from app.db.models import (
    Alert,
    Base,
    Item,
    PoLine,
    PurchaseOrder,
    Site,
    Supplier,
)
from app.main import create_app

_NOW = datetime(2026, 10, 17, 9, 0, 0, tzinfo=UTC)
_seq = itertools.count()


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _patch_session(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    monkeypatch.setattr(items_api, "SessionLocal", lambda: session)


def _seed_site(session: Session, code: str = "SITE") -> str:
    n = next(_seq)
    session.add(Site(code=f"{code}-{n}", name=f"Site {n}"))
    session.flush()
    return session.query(Site).filter_by(code=f"{code}-{n}").one().id


def _seed_item(session: Session, sku: str = "ITEM") -> str:
    n = next(_seq)
    session.add(
        Item(
            sku=f"{sku}-{n}",
            name=f"Item {n}",
            uom="EA",
            criticality="A",
            moq=10,
            lot_multiple=1,
            stockout_cost=500.0,
            service_level=0.95,
        )
    )
    session.flush()
    return session.query(Item).filter_by(sku=f"{sku}-{n}").one().id


def _seed_supplier(session: Session, code: str = "SUP") -> str:
    n = next(_seq)
    session.add(Supplier(code=f"{code}-{n}", name=f"Supplier {n}", active=True))
    session.flush()
    return session.query(Supplier).filter_by(code=f"{code}-{n}").one().id


def _seed_po(
    session: Session,
    supplier_id: str,
    item_id: str,
    site_id: str,
    status: str = "open",
) -> str:
    n = next(_seq)
    po = PurchaseOrder(
        po_number=f"PO-{n:04d}",
        supplier_id=supplier_id,
        site_id=site_id,
        status=status,
        order_date=_NOW.replace(tzinfo=None) - timedelta(days=10),
        promised_date=_NOW.replace(tzinfo=None) + timedelta(days=5),
    )
    session.add(po)
    session.flush()
    session.add(
        PoLine(po_id=po.id, item_id=item_id, qty_ordered=50.0)
    )
    session.flush()
    return po.id


def _seed_alert(
    session: Session,
    item_id: str,
    supplier_id: str | None,
    site_id: str,
    severity: str = "high",
) -> str:
    n = next(_seq)
    alert = Alert(
        item_id=item_id,
        supplier_id=supplier_id,
        site_id=site_id,
        type="stockout_risk",
        severity=severity,
        status="open",
        score=150.0,
        expected_loss=250.0,
        dedupe_key=f"alert-{n}",
        created_at=_NOW.replace(tzinfo=None) - timedelta(days=n),
    )
    session.add(alert)
    session.flush()
    return alert.id


# ---------------- tests ----------------


def test_get_item_detail_returns_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    item_id = _seed_item(session, "SKU-1")
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "viewer"
    }
    client = TestClient(app)
    resp = client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == item_id
    assert body["criticality"] == "A"
    assert body["service_level"] == 0.95
    assert body["moq"] == 10.0
    assert body["unit_cost"] is None


def test_get_item_detail_with_forecast_and_alerts_and_pos(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    site_id = _seed_site(session, "SITE-2")
    item_id = _seed_item(session, "SKU-2")
    sup_id = _seed_supplier(session, "SUP-2")
    _seed_po(session, sup_id, item_id, site_id, status="open")
    _seed_alert(session, item_id, sup_id, site_id, severity="high")
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "viewer"
    }
    client = TestClient(app)
    resp = client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == item_id
    assert body["forecast"] is not None
    assert "forecast" in body["forecast"]
    assert "method" in body["forecast"]
    assert len(body["alert_history"]) == 1
    assert body["alert_history"][0]["severity"] == "high"
    assert len(body["open_pos"]) == 1


def test_get_item_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    session.commit()
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "viewer"
    }
    client = TestClient(app)
    resp = client.get("/api/v1/items/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_get_item_denied_for_unknown_role(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    _seed_site(session, "SITE-3")
    item_id = _seed_item(session, "SKU-3")
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "auditor"
    }
    client = TestClient(app)
    resp = client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 403