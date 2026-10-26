"""Shared helpers for API tests: dependency overrides for auth + CSRF.

Tests that exercise routes through TestClient normally override
``get_current_user`` (role) and ``verify_csrf`` (header presence). The real
auth+CSRF behavior is pinned separately in tests/unit/test_auth_flow.py,
which never uses these helpers.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.core.dependencies import get_current_user, verify_csrf

ROLE_USER: dict[str, str | None] = {
    "id": "user-1",
    "username": "user-1",
    "role": "planner",
}


def override_auth(app: FastAPI, role: str = "planner", user_id: str = "user-1") -> None:
    """Allow requests through get_current_user + verify_csrf in tests."""
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "username": user_id,
        "role": role,
    }
    app.dependency_overrides[verify_csrf] = lambda: None


def override_role(app: FastAPI, role: str) -> None:
    """Change only the acting role (auth+CSRF overrides already installed)."""
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "username": "user-1",
        "role": role,
    }


def user_payload(role: str) -> dict[str, str | None]:
    """Return one {id, username, role} payload shape used by route deps."""
    u: dict[str, Any] = {"id": "user-1", "username": "user-1", "role": role}
    return u
