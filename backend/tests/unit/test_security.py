"""P1-03 tests: hashing, RBAC, lockout."""

from __future__ import annotations

import pytest

from app.core.security import LockoutTracker, can_access, hash_password, verify_password


def test_hash_roundtrip() -> None:
    h = hash_password("a-strong-pass-01")
    assert verify_password(h, "a-strong-pass-01")
    assert not verify_password(h, "wrong-password-99")


def test_hash_rejects_short_and_common() -> None:
    with pytest.raises(ValueError):
        hash_password("short1")
    with pytest.raises(ValueError):
        hash_password("password1234")


def test_rbac_admin_can_all_viewer_limited() -> None:
    assert can_access("admin", "viewer")
    assert can_access("admin", "admin")
    assert can_access("planner", "viewer")
    assert not can_access("viewer", "planner")
    assert not can_access("viewer", "admin")
    assert not can_access("purchaser", "admin")
    assert not can_access("nobody", "viewer")


def test_lockout_after_five() -> None:
    t = LockoutTracker(max_failures=5)
    for _ in range(4):
        t.record_failure("u1")
        assert not t.is_locked("u1")
    t.record_failure("u1")
    assert t.is_locked("u1")
    t.record_success("u1")
    assert not t.is_locked("u1")
