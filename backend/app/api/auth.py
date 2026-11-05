"""Authentication endpoints (spec PART L): login, logout, me.

Sessions use HTTP-only Secure SameSite=Strict cookies plus a CSRF token
required on non-GET requests (router-level dependency). No default
passwords; first run forces admin creation via POST /auth/login when the
users table is empty. Login attempts are lockout-tracked and every auth
event lands in the hash-chained audit log.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.audit import append_entry
from app.core.dependencies import get_current_user
from app.core.security import LockoutTracker, hash_password, verify_password
from app.core.session import create_access_token
from app.db.models import User
from app.db.session import SessionLocal

# Base path is /api/v1 per api-spec A0; PART L paths mount under it.
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_lockout = LockoutTracker(
    max_failures=settings.login_lockout_failures,
    window_minutes=settings.login_lockout_minutes,
)


class LoginRequest(BaseModel):
    """Login body: credentials travel in the request body, never the URL."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=settings.environment == "prod",
        samesite="strict",
        path="/",
        max_age=settings.session_idle_minutes * 60,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key="session", path="/")


def _audit(
    session_obj: Session,
    event_type: str,
    username: str,
    outcome: str,
    actor_id: str | None = None,
) -> None:
    """Write one auth event to the hash-chained audit log (hard rule 5)."""
    payload: dict[str, object]
    if outcome.startswith("failure:"):
        _, reason = outcome.split(":", 1)
        payload = {"outcome": "failure", "reason": reason}
    else:
        payload = {"outcome": outcome}
    append_entry(
        session_obj,
        actor_type="user",
        actor_id=actor_id,
        event_type=event_type,
        entity_type="user",
        entity_id=username,
        payload=payload,
    )


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def login(response: Response, body: LoginRequest) -> None:
    """Authenticate a user and issue a session cookie.

    Credentials arrive as a JSON body (never query strings). On the very
    first login with no users at all, the submitted credentials create the
    initial admin account. Failures are lockout-tracked and audited.
    """
    username = body.username
    session = SessionLocal()
    try:
        if _lockout.is_locked(username):
            _audit(session, "auth.login_failed", username, "failure:locked")
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="account locked after repeated failures",
            )
        user = session.scalars(select(User).where(User.username == username)).first()
        if user is None:
            # First-run bootstrap: create the admin account.
            existing = session.scalars(select(User)).first()
            if existing is not None:
                _audit(session, "auth.login_failed", username, "failure:bad_credentials")
                session.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="invalid credentials",
                )
            try:
                password_hash = hash_password(body.password)
            except ValueError as exc:
                _audit(session, "auth.login_failed", username, "failure:weak_password")
                session.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
            user = User(
                username=username,
                password_hash=password_hash,
                full_name=username,
                role="admin",
                active=True,
            )
            session.add(user)
            try:
                session.commit()
            except IntegrityError:
                # Concurrent bootstrap: another request created the admin first.
                session.rollback()
                user = session.scalars(select(User).where(User.username == username)).first()
                if user is None or not verify_password(user.password_hash, body.password):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="invalid credentials",
                    ) from None
            else:
                _audit(session, "auth.bootstrap_admin", username, "success", actor_id=user.id)
                session.commit()
        elif not verify_password(user.password_hash, body.password):
            # Password check comes first so account state is never disclosed
            # to someone without valid credentials.
            failures = _lockout.record_failure(username)
            reason = "bad_credentials"
            if _lockout.is_locked(username):
                reason = f"locked_after_{failures}_failures"
            _audit(session, "auth.login_failed", username, f"failure:{reason}")
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid credentials",
            )
        elif not user.active:
            _audit(session, "auth.login_failed", username, "failure:disabled")
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="account disabled",
            )

        _lockout.record_success(username)
        token = create_access_token(user.id, user.username, user.role)
        _set_session_cookie(response, token)
        _audit(session, "auth.login", username, "success", actor_id=user.id)
        session.commit()
    finally:
        session.close()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout(
    response: Response,
    user: dict[str, str | None] = Depends(get_current_user),  # noqa: B008
) -> None:
    """Require a valid session, audit it, and clear the session cookie."""
    session = SessionLocal()
    try:
        username = user.get("username") or "unknown"
        append_entry(
            session,
            actor_type="user",
            actor_id=user.get("id"),
            event_type="auth.logout",
            entity_type="user",
            entity_id=username,
            payload={"outcome": "success"},
        )
        session.commit()
    finally:
        session.close()
    _clear_session_cookie(response)


@router.get("/me", response_model=dict[str, Any])
def me(user: dict[str, str | None] = Depends(get_current_user)) -> dict[str, Any]:  # noqa: B008
    """Return the authenticated user's profile."""
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
    }


@router.get("/roles", response_model=list[str])
def roles() -> list[str]:
    """Return the list of valid roles (public info for UI role pickers)."""
    return ["admin", "planner", "purchaser", "viewer"]
