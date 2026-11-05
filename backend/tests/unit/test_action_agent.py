"""Action execution gates (P4-05/P4-06, acceptance D1).

At least fifteen negative cases prove that no write can happen when the role,
state, autonomy level, limits, global switch or connector flag says no.
"""

from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import action_agent
from app.config import settings
from app.connectors.base import WriteResult
from app.core import autonomy
from app.db.models import (
    Action,
    Alert,
    AuditLog,
    Base,
    Connector,
    Item,
    PoLine,
    PurchaseOrder,
    Recommendation,
    Setting,
    Site,
    Supplier,
)

_NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)
_seq = itertools.count()
_LIMITS = {
    "max_value_per_action": 100_000,
    "max_qty": 500,
    "allowed_supplier_ids": ["PLACEHOLDER"],
    "allowed_item_criticality": ["A", "B", "C"],
    "daily_action_cap": 50,
}


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(
    session: Session,
    *,
    status: str = "approved",
    action_type: str = "create_draft_po",
    payload_extra: dict[str, object] | None = None,
) -> tuple[str, str]:
    """Seed one alert + recommendation; returns (rec_id, supplier_id)."""
    n = next(_seq)
    site = Site(code=f"P4-S{n}", name=f"Plant {n}")
    sup = Supplier(code=f"P4-SUP{n}", name="Acme Steels", active=True)
    item = Item(
        sku=f"P4-BOLT-{n}",
        name="Hex Bolt",
        uom="EA",
        unit_cost=250.0,
        criticality="A",
        moq=100.0,
        lot_multiple=50.0,
    )
    session.add_all([site, sup, item])
    session.flush()
    po = PurchaseOrder(
        po_number=f"P4-PO-{n}",
        supplier_id=sup.id,
        site_id=site.id,
        order_date=datetime(2026, 1, 1, tzinfo=UTC),
        promised_date=datetime(2026, 1, 16, tzinfo=UTC),
        status="open",
    )
    session.add(po)
    session.flush()
    session.add(
        PoLine(po_id=po.id, item_id=item.id, qty_ordered=100.0, qty_received=0.0, unit_price=250.0)
    )
    alert = Alert(
        item_id=item.id,
        site_id=site.id,
        supplier_id=sup.id,
        type="supplier_delay",
        severity="high",
        expected_loss=240000.0,
        score=80.0,
        status="open",
        dedupe_key=f"p4-alert-{n}",
    )
    session.add(alert)
    session.flush()
    payload: dict[str, object] = {
        "supplier_id": sup.id,
        "supplier_name": "Acme Steels",
        "item_id": item.id,
        "sku": item.sku,
        "qty": 100.0,
        "unit_cost": 250.0,
        "est_cost": 25000.0,
        "criticality": "A",
    }
    if payload_extra:
        payload.update(payload_extra)
    rec = Recommendation(
        display_id=n + 1,
        alert_id=alert.id,
        action_type=action_type,
        payload=json.dumps(payload),
        est_cost=25000.0,
        est_benefit=240000.0,
        benefit_label="estimate",
        autonomy_level=2,
        status=status,
        decided_at=_NOW if status != "pending" else None,
        decided_by="user-1" if status != "pending" else None,
    )
    session.add(rec)
    session.commit()
    return rec.id, sup.id


def _ready_level3(session: Session, supplier_id: str, *, qty_cap: float = 500) -> None:
    installed = datetime.now(UTC) - timedelta(days=60)
    session.add(Setting(key="system.installed_at", value=installed.isoformat()))
    session.commit()
    autonomy.set_limits(
        session,
        {
            **_LIMITS,
            "allowed_supplier_ids": [supplier_id],
            "max_qty": qty_cap,
        },
        "admin-1",
    )
    autonomy.set_level(session, "create_draft_po", 3, "admin-1", acknowledge_level3=True)
    session.commit()


class _FakeConnector:
    def __init__(self, *, ok: bool = True, raises: bool = False) -> None:
        self.ok = ok
        self.raises = raises

    def write(self, session: Session, payload: dict[str, object]) -> WriteResult:
        if self.raises:
            raise RuntimeError("connector exploded")
        if not self.ok:
            return WriteResult(ok=False, reference="", message="remote rejected")
        return WriteResult(ok=True, reference="ZOHO-PO-77", message="created")


def _connector(session: Session, *, write_enabled: bool = True, kind: str = "zoho") -> str:
    row = Connector(
        name=f"conn-{next(_seq)}",
        type=kind,
        config_encrypted=b"",
        write_enabled=write_enabled,
    )
    session.add(row)
    session.commit()
    return row.id


def _statuses(session: Session) -> list[str]:
    return [a.status for a in session.query(Action).order_by(Action.id).all()]


# ---- successful outbox path ------------------------------------------------
def test_approved_recommendation_executes_to_outbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, _ = _seed(session)

    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="planner", now=_NOW
    )
    session.commit()

    assert outcome.status == "executed"
    assert outcome.target == "outbox"
    assert outcome.reference is not None
    assert (tmp_path / "outbox" / outcome.reference).is_file()
    rec = session.get(Recommendation, rec_id)
    assert rec is not None and rec.status == "executed"
    assert _statuses(session) == ["executed"]
    assert session.query(AuditLog).filter_by(event_type="action.executed").count() == 1


# ---- negative: role / state ------------------------------------------------
@pytest.mark.parametrize("role", ["viewer", "", "unknown"])
def test_viewer_or_unknown_role_cannot_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, _ = _seed(session)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role=role, now=_NOW
    )
    assert outcome.status == "blocked"
    assert session.get(Recommendation, rec_id).status == "approved"  # type: ignore[union-attr]


@pytest.mark.parametrize("state", ["rejected", "executed", "failed", "cancelled"])
def test_non_approved_states_are_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, _ = _seed(session, status=state)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin", now=_NOW
    )
    assert outcome.status == "blocked"
    assert state in outcome.message


# ---- negative: autonomy ----------------------------------------------------
def test_pending_level_one_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, _ = _seed(session, status="pending")
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="planner", now=_NOW
    )
    assert outcome.status == "blocked"
    assert "level 1" in outcome.message
    assert session.get(Recommendation, rec_id).status == "pending"  # type: ignore[union-attr]


def test_pending_level_two_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, _ = _seed(session, status="pending")
    autonomy.set_level(session, "create_draft_po", 2, "admin-1")
    session.commit()
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="planner", now=_NOW
    )
    assert outcome.status == "blocked"
    assert "requires approval" in outcome.message


def test_pending_level_three_over_limit_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, supplier_id = _seed(session, status="pending", payload_extra={"qty": 501.0})
    _ready_level3(session, supplier_id)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="planner", now=_NOW
    )
    assert outcome.status == "blocked"
    assert "outside limits" in outcome.message
    assert session.get(Recommendation, rec_id).status == "pending"  # type: ignore[union-attr]


def test_pending_level_three_within_limits_auto_approves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, supplier_id = _seed(session, status="pending")
    _ready_level3(session, supplier_id)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id=None, actor_role="admin", now=_NOW
    )
    session.commit()
    assert outcome.status == "executed"
    rec = session.get(Recommendation, rec_id)
    assert rec is not None and rec.status == "executed"
    assert rec.decided_by == "system:autonomy-l3"
    assert session.query(AuditLog).filter_by(event_type="recommendation.auto_approved").count() == 1


# ---- negative: connector gates --------------------------------------------
def test_connector_write_disabled_globally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", False)
    session = _session()
    rec_id, _ = _seed(session)
    conn_id = _connector(session)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    assert outcome.status == "blocked"
    assert "disabled" in outcome.message


@pytest.mark.parametrize(
    "case,expected",
    [
        ("missing_id", "connector_id is required"),
        ("not_found", "connector not found"),
    ],
)
def test_connector_identity_gates(
    monkeypatch: pytest.MonkeyPatch, case: str, expected: str
) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", True)
    session = _session()
    rec_id, _ = _seed(session)
    conn_id = None if case == "missing_id" else "does-not-exist"
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    assert outcome.status == "blocked"
    assert expected in outcome.message


def test_connector_row_write_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", True)
    session = _session()
    rec_id, _ = _seed(session)
    conn_id = _connector(session, write_enabled=False)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    assert outcome.status == "blocked"
    assert "not enabled" in outcome.message


def test_read_only_connector_type_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", True)
    session = _session()
    rec_id, _ = _seed(session)
    conn_id = _connector(session, write_enabled=True, kind="csv")
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    assert outcome.status == "blocked"
    assert "read-only" in outcome.message


def test_connector_rejects_non_po_action(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", True)
    session = _session()
    rec_id, _ = _seed(session, action_type="draft_supplier_message")
    conn_id = _connector(session)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    assert outcome.status == "blocked"
    assert "no connector write path" in outcome.message


def test_connector_success_marks_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", True)
    monkeypatch.setattr(action_agent, "build_connector", lambda row: _FakeConnector())
    session = _session()
    rec_id, _ = _seed(session)
    conn_id = _connector(session)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    session.commit()
    assert outcome.status == "executed"
    assert outcome.reference == "ZOHO-PO-77"
    assert session.get(Recommendation, rec_id).status == "executed"  # type: ignore[union-attr]


def test_connector_exception_records_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", True)
    monkeypatch.setattr(
        action_agent, "build_connector", lambda row: _FakeConnector(raises=True)
    )
    session = _session()
    rec_id, _ = _seed(session)
    conn_id = _connector(session)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    session.commit()
    assert outcome.status == "failed"
    assert session.get(Recommendation, rec_id).status == "failed"  # type: ignore[union-attr]
    assert _statuses(session) == ["failed"]


def test_connector_rejection_records_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "erp_write_enabled", True)
    monkeypatch.setattr(action_agent, "build_connector", lambda row: _FakeConnector(ok=False))
    session = _session()
    rec_id, _ = _seed(session)
    conn_id = _connector(session)
    outcome = action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="admin",
        target="connector", connector_id=conn_id, now=_NOW,
    )
    assert outcome.status == "failed"
    assert outcome.message == "remote rejected"


# ---- malformed requests ----------------------------------------------------
def test_unknown_target_raises() -> None:
    session = _session()
    rec_id, _ = _seed(session)
    with pytest.raises(action_agent.ExecutionError, match="unknown execution target"):
        action_agent.execute_recommendation(
            session, rec_id, actor_id="u-1", actor_role="admin", target="email"
        )


def test_missing_recommendation_raises() -> None:
    session = _session()
    with pytest.raises(action_agent.ExecutionError, match="not found"):
        action_agent.execute_recommendation(
            session, "nope", actor_id="u-1", actor_role="admin"
        )


def test_list_actions_filters_by_recommendation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    session = _session()
    rec_id, _ = _seed(session)
    action_agent.execute_recommendation(
        session, rec_id, actor_id="u-1", actor_role="planner", now=_NOW
    )
    session.commit()
    assert len(action_agent.list_actions(session, rec_id)) == 1
    assert action_agent.list_actions(session, "other") == []
