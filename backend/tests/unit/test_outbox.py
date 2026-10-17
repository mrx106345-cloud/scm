"""Outbox export tests (P3-05): outbox.write tool + list/download API routes.

Covers XLSX/CSV/TXT generation, formula-injection sanitization, the
system-generated filename allow-list, the approved-only gate, audit entries
for export/download, and role enforcement on GET /outbox and download.
"""

from __future__ import annotations

import csv
import io
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import outbox as outbox_api
from app.config import settings
from app.connectors import outbox as outbox_service
from app.core.dependencies import get_current_user
from app.db.models import (
    Alert,
    Base,
    Item,
    PoLine,
    PurchaseOrder,
    Recommendation,
    Site,
    Supplier,
)
from app.main import create_app

_NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)
_seq = itertools.count()


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_approved(
    session: Session,
    action_type: str = "create_draft_po",
    status: str = "approved",
    payload_extra: dict[str, object] | None = None,
) -> str:
    n = next(_seq)
    site = Site(code=f"S1-{n}", name=f"Plant {n}")
    sup = Supplier(code=f"SUP-{n}", name="Acme Steels", active=True)
    item = Item(
        sku=f"BOLT-M8-{n}",
        name="Hex Bolt",
        uom="EA",
        unit_cost=250.0,
        moq=100.0,
        lot_multiple=50.0,
    )
    session.add_all([site, sup, item])
    session.flush()
    po = PurchaseOrder(
        po_number=f"PO-100-{n}",
        supplier_id=sup.id,
        site_id=site.id,
        order_date=datetime(2026, 1, 1, tzinfo=UTC),
        promised_date=datetime(2026, 1, 16, tzinfo=UTC),
        status="open",
    )
    session.add(po)
    session.flush()
    session.add(
        PoLine(
            po_id=po.id,
            item_id=item.id,
            qty_ordered=100.0,
            qty_received=0.0,
            unit_price=250.0,
        )
    )
    session.flush()
    session.add(
        Alert(
            item_id=item.id,
            site_id=site.id,
            supplier_id=sup.id,
            type="supplier_delay",
            severity="high",
            expected_loss=240000.0,
            score=80.0,
            status="open",
            dedupe_key=f"alert:seed:{n}",
        )
    )
    session.flush()
    alert_id = session.query(Alert).filter_by(dedupe_key=f"alert:seed:{n}").one().id
    payload = {
        "supplier_id": sup.id,
        "item_id": item.id,
        "qty": 100.0,
        "unit_price": "250.00",
        "need_by_date": None,
        "message_text": "Please confirm the expected delivery date.",
    }
    if payload_extra:
        payload.update(payload_extra)
    rec = Recommendation(
        display_id=n + 1,
        alert_id=alert_id,
        action_type=action_type,
        payload=json.dumps(payload),
        est_cost=25000.0,
        est_benefit=240000.0,
        benefit_label="estimate",
        autonomy_level=2,
        status=status,
        decided_at=_NOW,
        decided_by="user-1",
    )
    session.add(rec)
    session.commit()
    return rec.id


def _audit_event_ids(session: Session, event_type: str) -> list[str]:
    from app.db.models import AuditLog

    return [
        r.entity_id
        for r in session.query(AuditLog)
        .filter_by(event_type=event_type)
        .order_by(AuditLog.id)
        .all()
    ]


def _seq_display(session: Session, rec_id: str) -> int:
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise ValueError(f"recommendation {rec_id} not found")
    return rec.display_id


def test_write_export_xlsx_creates_file_and_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id = _seed_approved(session, "create_draft_po")

    ofile = outbox_service.write_export(
        session, rec_id, file_type="xlsx", actor_id="user-1", now=_NOW
    )
    session.commit()

    assert ofile.file_type == "xlsx"
    assert ofile.recommendation_id == rec_id
    assert ofile.size_bytes > 0
    assert ofile.filename == f"PO_{_seq_display(session, rec_id)}_20261016T120000Z.xlsx"
    assert (tmp_path / "outbox" / ofile.filename).is_file()

    wb = load_workbook(tmp_path / "outbox" / ofile.filename)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0][0] == "recommendation_id"
    assert rows[1][0] == rec_id
    assert "qty" in rows[0]
    assert rows[1][rows[0].index("qty")] == "100.0"

    export_ids = _audit_event_ids(session, "outbox.export")
    assert len(export_ids) == 1
    assert export_ids[0] == ofile.id


def test_write_export_csv_and_txt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id = _seed_approved(session, "draft_supplier_message")

    csv_file = outbox_service.write_export(
        session, rec_id, file_type="csv", actor_id="user-1", now=_NOW
    )
    txt_file = outbox_service.write_export(
        session, rec_id, file_type="txt", actor_id="user-1", now=_NOW
    )
    session.commit()

    assert csv_file.filename.endswith(".csv")
    assert txt_file.filename.endswith(".txt")
    assert csv_file.filename.startswith(f"PO_{_seq_display(session, rec_id)}_")

    with open(tmp_path / "outbox" / csv_file.filename, newline="", encoding="utf-8") as fh:
        reader = list(csv.reader(fh))
    assert reader[0][0] == "recommendation_id"
    assert reader[1][0] == rec_id

    text = (tmp_path / "outbox" / txt_file.filename).read_text(encoding="utf-8")
    assert text.startswith("recommendation_id,")
    assert rec_id in text.splitlines()[1]


def test_write_export_requires_approved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()

    pending_id = _seed_approved(session, "create_draft_po", status="pending")
    with pytest.raises(ValueError, match="not approved"):
        outbox_service.write_export(session, pending_id, now=_NOW)

    rejected_id = _seed_approved(session, "draft_supplier_message", status="rejected")
    with pytest.raises(ValueError, match="not approved"):
        outbox_service.write_export(session, rejected_id, now=_NOW)
    assert not (tmp_path / "outbox").exists()


def test_write_export_unknown_recommendation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    with pytest.raises(FileNotFoundError, match="not found"):
        outbox_service.write_export(session, "00000000-0000-0000-0000-000000000000", now=_NOW)


def test_formula_cells_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id = _seed_approved(
        session,
        "create_draft_po",
        payload_extra={
            "note": "=cmd(1)",
            "plus": "+1",
            "at": "@x",
            "tab": "\ttabbed",
            "safe": "ordinary text",
        },
    )
    ofile = outbox_service.write_export(session, rec_id, file_type="csv", now=_NOW)
    session.commit()

    with open(tmp_path / "outbox" / ofile.filename, newline="", encoding="utf-8") as fh:
        reader = list(csv.reader(fh))
    header = reader[0]
    row = reader[1]
    assert row[header.index("note")] == "'=cmd(1)"
    assert row[header.index("plus")] == "'+1"
    assert row[header.index("at")] == "'@x"
    assert row[header.index("tab")] == "'\ttabbed"
    assert row[header.index("safe")] == "ordinary text"


def test_export_is_hash_chained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id = _seed_approved(session, "create_draft_po")

    outbox_service.write_export(session, rec_id, actor_id="user-1", now=_NOW)
    outbox_service.write_export(session, rec_id, file_type="csv", actor_id="user-2", now=_NOW)
    session.commit()

    from app.db.models import AuditLog

    rows = session.query(AuditLog).filter_by(event_type="outbox.export").order_by(AuditLog.id).all()
    assert len(rows) == 2
    assert rows[0].prev_hash == "0" * 64
    assert rows[1].prev_hash == rows[0].hash
    assert rows[1].hash != rows[0].hash


def test_list_and_get_outbox_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id = _seed_approved(session, "create_draft_po")

    xlsx = outbox_service.write_export(session, rec_id, file_type="xlsx", now=_NOW)
    csv_file = outbox_service.write_export(session, rec_id, file_type="csv", now=_NOW)
    session.commit()

    files = outbox_service.list_outbox_files(session)
    assert len(files) == 2
    assert {f.id for f in files} == {xlsx.id, csv_file.id}

    got = outbox_service.get_outbox_file(session, xlsx.id)
    assert got is not None
    assert got.filename == xlsx.filename
    assert got.file_type == "xlsx"
    assert outbox_service.get_outbox_file(session, "missing-id") is None


# ---------------- API routes ----------------


def _patch_session(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    monkeypatch.setattr(outbox_api, "SessionLocal", lambda: session)


def test_api_list_outbox_planner_and_purchaser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    _patch_session(monkeypatch, session)
    rec_id = _seed_approved(session, "create_draft_po")
    outbox_service.write_export(session, rec_id, now=_NOW)
    session.commit()

    for role in ("planner", "purchaser", "admin"):
        result = outbox_api.list_outbox(user={"id": "user-1", "username": "user-1", "role": role})
        assert len(result) == 1
        assert result[0].name.endswith(".xlsx")
        assert result[0].type == "xlsx"
        assert result[0].recommendation_id == rec_id
        assert result[0].created_at is not None


def test_api_list_outbox_viewer_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    _patch_session(monkeypatch, session)
    _seed_approved(session, "create_draft_po")
    session.commit()

    with pytest.raises(HTTPException) as exc:
        outbox_api.list_outbox(user={"id": "user-1", "username": "user-1", "role": "viewer"})
    assert exc.value.status_code == 403


def test_api_download_outbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    _patch_session(monkeypatch, session)
    rec_id = _seed_approved(session, "create_draft_po")
    ofile = outbox_service.write_export(session, rec_id, file_type="xlsx", now=_NOW)
    session.commit()

    app = create_app()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "username": "user-1",
        "role": "planner",
    }
    resp = client.get(f"/api/v1/outbox/{ofile.id}/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert f'filename="{ofile.filename}"' in resp.headers.get("content-disposition", "")

    wb = load_workbook(io.BytesIO(resp.content))
    assert wb.active.cell(row=1, column=1).value == "recommendation_id"

    # Download is audited.
    assert ofile.id in _audit_event_ids(session, "outbox.download")


def test_api_download_outbox_missing_and_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    _patch_session(monkeypatch, session)
    session.commit()

    app = create_app()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "username": "user-1",
        "role": "planner",
    }
    resp = client.get("/api/v1/outbox/00000000-0000-0000-0000-000000000000/download")
    assert resp.status_code == 404

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "username": "user-1",
        "role": "viewer",
    }
    resp = client.get(
        "/api/v1/outbox/00000000-0000-0000-0000-000000000000/download",
    )
    assert resp.status_code == 403
