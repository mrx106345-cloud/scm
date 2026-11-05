"""Autonomy levels, limits and level-3 gates (P4-05, Part I.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import autonomy
from app.db.models import Action, AuditLog, Base, Setting

_LIMITS = {
    "max_value_per_action": 100_000,
    "max_qty": 500,
    "allowed_supplier_ids": ["sup-1"],
    "allowed_item_criticality": ["A", "B"],
    "daily_action_cap": 3,
}


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _mature_install(session: Session, days: int = 60) -> None:
    installed = datetime.now(UTC) - timedelta(days=days)
    session.add(Setting(key="system.installed_at", value=installed.isoformat()))
    session.commit()


def _ready_level3(session: Session) -> None:
    _mature_install(session)
    autonomy.set_limits(session, _LIMITS, "admin-1")
    autonomy.set_level(session, "create_draft_po", 3, "admin-1", acknowledge_level3=True)
    session.commit()


def test_default_level_is_one() -> None:
    session = _session()
    for action_type in autonomy.ACTION_TYPES:
        assert autonomy.get_level(session, action_type) == 1


def test_unknown_action_type_rejected() -> None:
    session = _session()
    with pytest.raises(autonomy.AutonomyError, match="unknown action type"):
        autonomy.get_level(session, "send_money")


def test_invalid_stored_level_falls_back_to_one() -> None:
    session = _session()
    session.add(Setting(key="autonomy.create_draft_po", value='"9"'))
    session.commit()
    assert autonomy.get_level(session, "create_draft_po") == 1


def test_set_level_two() -> None:
    session = _session()
    autonomy.set_level(session, "create_draft_po", 2, "admin-1")
    session.commit()
    assert autonomy.get_level(session, "create_draft_po") == 2


def test_level_out_of_range_rejected() -> None:
    session = _session()
    for bad in (0, 4):
        with pytest.raises(autonomy.AutonomyError, match="level must be"):
            autonomy.set_level(session, "create_draft_po", bad, "admin-1")


def test_level_three_requires_all_limits() -> None:
    session = _session()
    _mature_install(session)
    with pytest.raises(autonomy.AutonomyError, match="missing limits"):
        autonomy.set_level(session, "create_draft_po", 3, "admin-1", acknowledge_level3=True)


def test_level_three_requires_thirty_days() -> None:
    session = _session()
    _mature_install(session, days=10)
    autonomy.set_limits(session, _LIMITS, "admin-1")
    with pytest.raises(autonomy.AutonomyError, match="days"):
        autonomy.set_level(session, "create_draft_po", 3, "admin-1", acknowledge_level3=True)


def test_level_three_requires_explicit_acknowledgment() -> None:
    session = _session()
    _mature_install(session)
    autonomy.set_limits(session, _LIMITS, "admin-1")
    with pytest.raises(autonomy.AutonomyError, match="acknowledgment"):
        autonomy.set_level(session, "create_draft_po", 3, "admin-1")


def test_level_three_enabled_with_ack_and_audited() -> None:
    session = _session()
    _ready_level3(session)
    assert autonomy.get_level(session, "create_draft_po") == 3
    ack = session.query(AuditLog).filter_by(event_type="autonomy.level3_acknowledged").all()
    assert len(ack) == 1
    assert autonomy.level3_readiness(session).level3_ready is True


def test_set_limits_rejects_unknown_key() -> None:
    session = _session()
    with pytest.raises(autonomy.AutonomyError, match="unknown limit keys"):
        autonomy.set_limits(session, {**_LIMITS, "max_users": 5}, "admin-1")


def test_set_limits_rejects_non_positive_numbers() -> None:
    session = _session()
    with pytest.raises(autonomy.AutonomyError, match="must be positive"):
        autonomy.set_limits(session, {**_LIMITS, "max_qty": 0}, "admin-1")


def test_set_limits_rejects_bad_criticality() -> None:
    session = _session()
    with pytest.raises(autonomy.AutonomyError, match="criticality"):
        autonomy.set_limits(session, {**_LIMITS, "allowed_item_criticality": ["X"]}, "admin-1")


def test_level_one_never_executes() -> None:
    session = _session()
    may_execute, level, reason = autonomy.decide_execution(
        session, "create_draft_po", {"qty": 1, "est_cost": 1, "supplier_id": "sup-1"}
    )
    assert may_execute is False
    assert level == 1
    assert "advise" in reason


def test_level_two_requires_approval() -> None:
    session = _session()
    autonomy.set_level(session, "create_draft_po", 2, "admin-1")
    may_execute, level, reason = autonomy.decide_execution(
        session, "create_draft_po", {"qty": 1, "est_cost": 1, "supplier_id": "sup-1"}
    )
    assert may_execute is False
    assert level == 2
    assert "approval" in reason


def test_level_three_within_limits_executes() -> None:
    session = _session()
    _ready_level3(session)
    may_execute, level, _ = autonomy.decide_execution(
        session,
        "create_draft_po",
        {"qty": 10, "est_cost": 5_000, "supplier_id": "sup-1", "criticality": "A"},
    )
    assert may_execute is True
    assert level == 3


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"qty": 10, "est_cost": 999_999, "supplier_id": "sup-1"}, "max_value_per_action"),
        ({"qty": 501, "est_cost": 10, "supplier_id": "sup-1"}, "max_qty"),
        ({"qty": 10, "est_cost": 10, "supplier_id": "sup-9"}, "supplier not allowed"),
        (
            {"qty": 10, "est_cost": 10, "supplier_id": "sup-1", "criticality": "C"},
            "criticality not allowed",
        ),
        ({"qty": "many", "est_cost": 10, "supplier_id": "sup-1"}, "qty not numeric"),
    ],
)
def test_level_three_outside_limits_falls_back(payload: dict[str, object], reason: str) -> None:
    session = _session()
    _ready_level3(session)
    may_execute, level, message = autonomy.decide_execution(
        session, "create_draft_po", payload
    )
    assert may_execute is False
    assert level == 3
    assert reason in message


def test_daily_action_cap_enforced() -> None:
    session = _session()
    _ready_level3(session)
    for _ in range(_LIMITS["daily_action_cap"]):
        session.add(
            Action(
                recommendation_id="rec-x",
                target="outbox",
                status="executed",
                result="{}",
            )
        )
    session.commit()
    may_execute, level, reason = autonomy.decide_execution(
        session, "create_draft_po", {"qty": 1, "est_cost": 1, "supplier_id": "sup-1"}
    )
    assert may_execute is False
    assert level == 3
    assert "daily action cap" in reason


def test_blocked_actions_do_not_consume_daily_cap() -> None:
    session = _session()
    _ready_level3(session)
    for _ in range(_LIMITS["daily_action_cap"] + 5):
        session.add(
            Action(
                recommendation_id="rec-x",
                target="outbox",
                status="blocked",
                result="{}",
            )
        )
    session.commit()
    may_execute, _, _ = autonomy.decide_execution(
        session, "create_draft_po", {"qty": 1, "est_cost": 1, "supplier_id": "sup-1"}
    )
    assert may_execute is True
