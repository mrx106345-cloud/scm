"""P0-01 tests: real auth flow over the /auth endpoints.

Unlike tests/helpers.override_auth users, these tests exercise the real
get_current_user / verify_csrf dependencies against a seeded in-memory DB:
JSON-body login, first-run bootstrap admin, sliding-window lockout, audit
trail linkage, and CSRF on state-changing requests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.auth as auth_mod
from app.core.audit import GENESIS_HASH, chain_hash
from app.core.security import LockoutTracker, hash_password
from app.db.models import AuditLog, Base, User
from app.main import create_app

CSRF = {"X-CSRF-Token": "t"}
GOOD = "Admin-Pw-2026!"

BAD_LOGIN = {
    "url": "/api/v1/auth/login",
    "bad_password": "nope-nopenope",
}


@pytest.fixture()
def client() -> TestClient:
    """App wired to an isolated in-memory users/audit DB (real auth deps)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    session = maker()
    session.add(
        User(
            username="admin",
            password_hash=hash_password(GOOD),
            full_name="Admin",
            role="admin",
            active=True,
        )
    )
    session.commit()

    real_local = auth_mod.SessionLocal
    auth_mod.SessionLocal = lambda: maker()  # noqa: E731
    app = create_app()
    # Reset module-global lockout state so tests are order-independent.
    auth_mod._lockout._failures.clear()  # noqa: SLF001 — test scaffolding
    try:
        yield TestClient(app)
    finally:
        auth_mod.SessionLocal = real_local
        auth_mod._lockout._failures.clear()  # noqa: SLF001 — test scaffolding


def _drop_users() -> None:
    """Empty the users table (first-run bootstrap scenarios)."""
    session = auth_mod.SessionLocal()
    try:
        session.query(User).delete()
        session.commit()
    finally:
        session.close()


def _rows() -> list[User]:
    """Fresh-session read of all users."""
    session = auth_mod.SessionLocal()
    try:
        return list(session.query(User).all())
    finally:
        session.close()


def _audit_rows(session: Session | None = None) -> list[dict[str, Any]]:
    """Fresh-session read of audit rows (optionally reusing a session)."""
    own = session is None
    s = session or auth_mod.SessionLocal()
    try:
        return [
            {
                "id": r.id,
                "event_type": r.event_type,
                "actor_id": r.actor_id,
                "entity_id": r.entity_id,
                "payload": json.loads(r.payload or "{}"),
                "prev_hash": r.prev_hash,
                "hash": r.hash,
                "ts": r.ts,
            }
            for r in s.query(AuditLog).order_by(AuditLog.id).all()
        ]
    finally:
        if own:
            s.close()


def _bad_login(client: TestClient, **body: str) -> Any:
    """One POST /auth/login with the bad password and a CSRF header."""
    payload: dict[str, str] = {"username": "admin", "password": BAD_LOGIN["bad_password"]}
    payload.update(body)
    return client.post("/api/v1/auth/login", json=payload, headers=CSRF)


def test_bootstrap_admin_first_login(client: TestClient) -> None:
    """Empty users table + login credentials create the initial admin."""
    _drop_users()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "first-admin", "password": GOOD},
        headers=CSRF,
    )
    assert resp.status_code == 204, resp.text
    assert "session" in resp.cookies
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert len(_rows()) == 1

    rows = [r for r in _audit_rows() if r["entity_id"] == "first-admin"]
    assert [r["event_type"] for r in rows] == ["auth.bootstrap_admin", "auth.login"]
    assert all(r["payload"]["outcome"] == "success" for r in rows)


def test_login_json_body_wrong_password(client: TestClient) -> None:
    """Wrong password -> 401 invalid credentials + audited failure."""
    resp = _bad_login(client)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid credentials"
    rows = [r for r in _audit_rows() if r["event_type"] == "auth.login_failed"]
    assert len(rows) == 1
    assert rows[0]["payload"] == {"outcome": "failure", "reason": "bad_credentials"}


def test_lockout_429_after_threshold(client: TestClient) -> None:
    """5 failures lock the account: the 6th attempt is 429 even with the right password."""
    for _ in range(5):
        resp = _bad_login(client)
        assert resp.status_code == 401
    ok = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": GOOD}, headers=CSRF
    )
    assert ok.status_code == 429
    rows = [r["payload"] for r in _audit_rows() if r["event_type"] == "auth.login_failed"]
    assert rows[-2] == {"outcome": "failure", "reason": "locked_after_5_failures"}
    assert rows[-1] == {"outcome": "failure", "reason": "locked"}
    locked = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": GOOD},
        headers=CSRF,
    )
    assert locked.status_code == 429


def test_lockout_tracker_sliding_window() -> None:
    """Tracker unit behavior: failures older than the window stop counting."""
    tracker = LockoutTracker(max_failures=2, window_minutes=15)
    tracker.record_failure("x")
    expired = datetime.now(UTC) - timedelta(minutes=16)
    tracker._failures["x"] = [expired]  # noqa: SLF001 — simulate an old failure
    assert tracker.is_locked("x") is False  # old failure pruned out of the window
    tracker.record_failure("x")
    assert tracker.is_locked("x") is False  # 1 in-window failure < threshold
    tracker.record_failure("x")
    assert tracker.is_locked("x") is True  # 2 in-window failures = locked


def test_success_clears_failure_count(client: TestClient) -> None:
    """A successful login resets the counter: 4 fails + success stops the lock."""
    for _ in range(4):
        assert _bad_login(client).status_code == 401
    ok = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": GOOD}, headers=CSRF
    )
    assert ok.status_code == 204
    for _ in range(5):
        resp = _bad_login(client)
        assert resp.status_code == 401  # all bad; never locked again


def test_cookie_flags_and_me(client: TestClient) -> None:
    """Session cookie: HttpOnly, SameSite=strict, Path=/; /me returns the profile."""
    resp = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": GOOD}, headers=CSRF
    )
    assert resp.status_code == 204
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie
    me = client.get("/api/v1/auth/me")
    assert me.json()["username"] == "admin"
    assert me.json()["role"] == "admin"
    assert me.json()["id"]


def test_tampered_cookie_401(client: TestClient) -> None:
    """A forged or expired token is rejected on /auth/me (401, not 500)."""
    client.cookies.clear()
    client.cookies.set("session", "not.a.jwt")
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401


def test_csrf_required_on_post(client: TestClient) -> None:
    """State-changing requests without X-CSRF-Token are 403 before auth work."""
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": GOOD})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "missing CSRF token"
    # No login attempt was audited: the request never reached the service.
    assert _audit_rows() == []


def test_logout_requires_session(client: TestClient) -> None:
    """Logout without a session is 401; with one it is 204 and audited."""
    no_session = client.post("/api/v1/auth/logout", headers=CSRF)
    assert no_session.status_code == 401
    client.post("/api/v1/auth/login", json={"username": "admin", "password": GOOD}, headers=CSRF)
    out = client.post("/api/v1/auth/logout", headers=CSRF)
    assert out.status_code == 204
    rows = [r for r in _audit_rows() if r["event_type"] == "auth.logout"]
    assert len(rows) == 1
    assert rows[0]["payload"]["outcome"] == "success"
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401  # cookie cleared -> /me 401


def test_disabled_account_403_without_password_leak(client: TestClient) -> None:
    """Disabled account: valid password -> 403; wrong password -> generic 401."""
    session = auth_mod.SessionLocal()
    try:
        session.query(User).filter(User.username == "admin").update({"active": False})
        session.commit()
    finally:
        session.close()
    wrong = _bad_login(client)
    assert wrong.status_code == 401  # account state not disclosed without password
    rows = [r["payload"] for r in _audit_rows() if r["event_type"] == "auth.login_failed"]
    assert rows[-1]["reason"] == "bad_credentials"
    right = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": GOOD}, headers=CSRF
    )
    assert right.status_code == 403
    assert right.json()["detail"] == "account disabled"


def test_audit_chain_linkage_and_tamper_detection(client: TestClient) -> None:
    """Rows form a linked chain; recomputing with altered payload mismatches."""
    client.post("/api/v1/auth/login", json={"username": "admin", "password": GOOD}, headers=CSRF)
    _bad_login(client)
    chain = _audit_rows()
    assert chain
    running = GENESIS_HASH
    for row in chain:
        assert row["prev_hash"] == running
        running = row["hash"]

    # Tamper demo: any changed field in an entry changes its hash (and every
    # subsequent link breaks, which the prev_hash linkage above would expose).
    original = chain[0]
    altered = dict(original)
    altered["payload"] = {**original["payload"], "outcome": "failure"}
    entry = {
        "ts": original["ts"].isoformat(),
        "actor_type": "user",
        "actor_id": original["actor_id"],
        "event_type": original["event_type"],
        "entity_type": "user",
        "entity_id": original["entity_id"],
        "payload": altered["payload"],
    }
    assert chain_hash(original["prev_hash"], entry) != original["hash"]


def test_weak_bootstrap_password_400(client: TestClient) -> None:
    """First-run bootstrap refuses weak passwords with 400 and no cookie."""
    _drop_users()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "first-admin", "password": "short123"},
        headers=CSRF,
    )
    assert resp.status_code == 400
    assert "12 characters" in resp.json()["detail"]
    assert not resp.cookies.get("session")
    assert len(_rows()) == 0


def test_roles_endpoint_public(client: TestClient) -> None:
    """GET /auth/roles needs no session (public info for the login screen)."""
    client.cookies.clear()
    resp = client.get("/api/v1/auth/roles")
    assert resp.status_code == 200
    assert resp.json() == ["admin", "planner", "purchaser", "viewer"]
