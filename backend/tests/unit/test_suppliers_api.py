"""Supplier list + detail API tests (P3-07, spec supplier/item pages).

Covers supplier list with metrics, supplier detail with risk breakdown,
lead-time trend and items exposed, plus role enforcement on the routes.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import suppliers as suppliers_api
from app.core.dependencies import get_current_user
from app.db.models import (
    Base,
    Item,
    PoLine,
    PurchaseOrder,
    Receipt,
    Site,
    Supplier,
    SupplierMetrics,
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
    monkeypatch.setattr(suppliers_api, "SessionLocal", lambda: session)


def _seed_site(session: Session, code: str = "SITE") -> str:
    n = next(_seq)
    session.add(Site(code=f"{code}-{n}", name=f"Site {n}"))
    session.flush()
    return session.query(Site).filter_by(code=f"{code}-{n}").one().id


def _seed_supplier(session: Session, code: str = "SUP") -> str:
    n = next(_seq)
    session.add(
        Supplier(code=f"{code}-{n}", name=f"Supplier {n}", active=True, contract_lead_time_days=7)
    )
    session.flush()
    return session.query(Supplier).filter_by(code=f"{code}-{n}").one().id


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


def _seed_receipt(
    session: Session, supplier_id: str, item_id: str, site_id: str, days_ago: int, lead_days: float
) -> str:
    n = next(_seq)
    order_date = _NOW.replace(tzinfo=None) - timedelta(days=days_ago + int(lead_days))
    receipt_date = _NOW.replace(tzinfo=None) - timedelta(days=days_ago)
    po = PurchaseOrder(
        po_number=f"PO-R{n:04d}",
        supplier_id=supplier_id,
        site_id=site_id,
        status="closed",
        order_date=order_date,
        promised_date=order_date + timedelta(days=int(lead_days)),
    )
    session.add(po)
    session.flush()
    line = PoLine(po_id=po.id, item_id=item_id, qty_ordered=50.0)
    session.add(line)
    session.flush()
    receipt = Receipt(
        po_line_id=line.id,
        receipt_date=receipt_date,
        qty=50.0,
    )
    session.add(receipt)
    session.flush()
    return receipt.id


# ---------------- tests ----------------


def test_list_suppliers_returns_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    site_id = _seed_site(session, "SITE-A")
    sup_id = _seed_supplier(session, "SUP-A")
    item_id = _seed_item(session, "ITEM-1")
    _seed_po(session, sup_id, item_id, site_id)
    _patch_session(monkeypatch, session)

    session.add(
        SupplierMetrics(
            supplier_id=sup_id,
            mean_lt_recent=7.5,
            mean_lt_prior=6.0,
            drift_pct=0.25,
            on_time_rate=0.90,
            dependency_share=0.40,
            risk_score=52,
            trend_flag=True,
            details='{"key": "value"}',
        )
    )
    session.commit()

    app = create_app()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "username": "user-1",
        "role": "viewer",
    }
    resp = client.get("/api/v1/suppliers")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["code"].startswith("SUP-A")
    assert row["risk_score"] == 52
    assert row["on_time_rate"] == 0.90
    assert row["trend_flag"] is True


def test_list_suppliers_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    session.commit()
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "viewer"
    }
    client = TestClient(app)
    resp = client.get("/api/v1/suppliers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_suppliers_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    for i in range(5):
        _seed_supplier(session, f"SUP-P{i}")
    session.commit()
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "viewer"
    }
    client = TestClient(app)
    resp = client.get("/api/v1/suppliers?page=1&page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


def test_get_supplier_detail_with_metrics_and_trend(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    site_id = _seed_site(session, "SITE-D")
    sup_id = _seed_supplier(session, "SUP-D")
    item_id = _seed_item(session, "ITEM-D")
    _seed_po(session, sup_id, item_id, site_id)
    _seed_receipt(session, sup_id, item_id, site_id, days_ago=30, lead_days=7.0)
    _seed_receipt(session, sup_id, item_id, site_id, days_ago=15, lead_days=9.0)
    _seed_receipt(session, sup_id, item_id, site_id, days_ago=1, lead_days=11.0)
    _patch_session(monkeypatch, session)

    session.add(
        SupplierMetrics(
            supplier_id=sup_id,
            mean_lt_recent=9.0,
            mean_lt_prior=7.0,
            drift_pct=0.28,
            on_time_rate=0.85,
            dependency_share=0.50,
            risk_score=61,
            trend_flag=True,
            details="{}",
        )
    )
    session.commit()

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "viewer"
    }
    client = TestClient(app)
    resp = client.get(f"/api/v1/suppliers/{sup_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == sup_id
    assert body["code"].startswith("SUP-D")
    assert body["risk_breakdown"] is not None
    assert body["risk_breakdown"]["total_raw"] > 0
    assert len(body["lead_time_trend"]) == 3
    assert body["lead_time_trend"][0]["lead_days"] == 7.0
    assert body["lead_time_trend"][2]["lead_days"] == 11.0
    assert len(body["items_exposed"]) == 1
    assert body["items_exposed"][0]["item_id"] == item_id


def test_get_supplier_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    session.commit()
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "viewer"
    }
    client = TestClient(app)
    resp = client.get("/api/v1/suppliers/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_list_suppliers_denied_for_unknown_role(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    session.commit()
    _patch_session(monkeypatch, session)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1", "username": "user-1", "role": "auditor"
    }
    client = TestClient(app)
    resp = client.get("/api/v1/suppliers")
    assert resp.status_code == 403