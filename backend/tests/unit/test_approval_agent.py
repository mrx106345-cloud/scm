"""Approval service tests (P3-04): recommendation state machine + role enforcement."""

import itertools
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import approval_agent
from app.db.models import (
    Alert,
    AuditLog,
    Base,
    Item,
    PoLine,
    PurchaseOrder,
    Recommendation,
    Site,
    Supplier,
)

_seq = itertools.count()


def _d(days: float) -> datetime:
    return datetime(2026, 1, 1) + timedelta(days=days)


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(session: Session, action_type: str = "create_draft_po") -> str:
    n = next(_seq)
    site = Site(code=f"S1-{n}", name=f"Plant {n}")
    sup = Supplier(code=f"SUP-{n}", name="Acme Steels", active=True)
    item = Item(
        sku=f"BOLT-M8-{n}", name="Hex Bolt", uom="EA", unit_cost=250.0, moq=100.0, lot_multiple=50.0
    )
    session.add_all([site, sup, item])
    session.flush()
    po = PurchaseOrder(
        po_number=f"PO-100-{n}",
        supplier_id=sup.id,
        site_id=site.id,
        order_date=_d(-10),
        promised_date=_d(15),
        status="open",
    )
    session.add(po)
    session.flush()
    session.add(
        PoLine(po_id=po.id, item_id=item.id, qty_ordered=100.0, qty_received=0.0, unit_price=250.0)
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
    rec = Recommendation(
        display_id=n + 1,
        alert_id=alert_id,
        action_type=action_type,
        payload="{}",
        est_cost=25000.0,
        est_benefit=240000.0,
        benefit_label="estimate",
        autonomy_level=2,
        status="pending",
    )
    session.add(rec)
    session.commit()
    return rec.id


def test_approve_pending_and_audit(session: Session) -> None:
    rec_id = _seed(session, "create_draft_po")
    rec = approval_agent.decide(session, rec_id, "approve", actor_id="user-1", actor_role="planner")
    session.commit()
    assert rec.status == "approved"
    assert rec.decided_by == "user-1"
    assert rec.decided_at is not None

    rows = session.query(AuditLog).filter_by(entity_type="recommendation", entity_id=rec_id).all()
    assert len(rows) == 1
    assert rows[0].event_type == "recommendation.approved"
    assert rows[0].actor_id == "user-1"


def test_reject_and_edit_approve(session: Session) -> None:
    rec_id = _seed(session, "draft_supplier_message")
    rec = approval_agent.decide(
        session,
        rec_id,
        "edit_approve",
        actor_id="user-2",
        actor_role="purchaser",
        edited_payload='{"qty": 200}',
        comment="adjusted qty",
    )
    session.commit()
    assert rec.status == "approved"
    assert rec.edited_payload == '{"qty": 200}'
    assert rec.decision_comment == "adjusted qty"

    rows = session.query(AuditLog).filter_by(entity_id=rec_id).all()
    assert any(r.event_type == "recommendation.edit_approve" for r in rows)


def test_cannot_decide_non_pending(session: Session) -> None:
    rec_id = _seed(session, "create_draft_po")
    approval_agent.decide(session, rec_id, "reject", actor_id="user-1", actor_role="planner")
    session.commit()
    with pytest.raises(approval_agent.TransitionError):
        approval_agent.decide(session, rec_id, "approve", actor_id="user-1", actor_role="planner")


def test_not_found(session: Session) -> None:
    with pytest.raises(approval_agent.TransitionError):
        approval_agent.decide(
            session,
            "00000000-0000-0000-0000-000000000000",
            "approve",
            actor_id="user-1",
            actor_role="planner",
        )


def test_purchaser_role_limits(session: Session) -> None:
    rec_id = _seed(session, "create_draft_po")
    approval_agent.decide(
        session, rec_id, "approve", actor_id="p", actor_role="purchaser"
    )  # allowed
    session.commit()

    rec_id2 = _seed(session, "raise_reorder_request")
    with pytest.raises(approval_agent.TransitionError):
        approval_agent.decide(
            session, rec_id2, "approve", actor_id="p", actor_role="purchaser"
        )  # denied


def test_viewer_cannot_decide(session: Session) -> None:
    rec_id = _seed(session, "create_draft_po")
    with pytest.raises(approval_agent.TransitionError):
        approval_agent.decide(session, rec_id, "approve", actor_id="v", actor_role="viewer")


def test_admin_can_decide_any_type(session: Session) -> None:
    rec_id = _seed(session, "raise_reorder_request")
    rec = approval_agent.decide(session, rec_id, "reject", actor_id="a", actor_role="admin")
    session.commit()
    assert rec.status == "rejected"


def test_list_recommendations_filters(session: Session) -> None:
    _seed(session, "create_draft_po")
    _seed(session, "draft_supplier_message")
    pending = approval_agent.list_recommendations(session, status="pending")
    assert len(pending) == 2
    pos = approval_agent.list_recommendations(session, action_type="create_draft_po")
    assert len(pos) == 1
    messages = approval_agent.list_recommendations(session, action_type="draft_supplier_message")
    assert len(messages) == 1
