"""Authentication endpoints (spec PART L): login, logout, me.

Sessions use HTTP-only Secure SameSite=Strict cookies plus a CSRF token
required on non-GET requests. No default passwords; first run forces admin
creation via POST /auth/login when the users table is empty.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.config import settings
from app.core.dependencies import get_current_user
from app.core.security import hash_password, verify_password
from app.core.session import create_access_token
from app.db.models import User
from app.db.session import SessionLocal

router = APIRouter(prefix="/auth", tags=["auth"])

CSRF_HEADER_NAME = "X-CSRF-Token"


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


def _verify_csrf(request: Request) -> None:
    """Require CSRF token on non-GET requests."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    csrf_token = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="missing CSRF token",
        )


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(
    response: Response,
    request: Request,
    username: str,
    password: str,
) -> None:
    """Authenticate a user and issue a session cookie.

    Body: username, password (form-encoded or JSON).
    On first run with no users, creates the admin account from these
    credentials and grants the admin role.
    """
    _verify_csrf(request)
    session = SessionLocal()
    try:
        user = session.scalars(select(User).where(User.username == username)).first()
        if user is None:
            # First-run bootstrap: create the admin account.
            existing = session.scalars(select(User)).first()
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="invalid credentials",
                )
            user = User(
                username=username,
                password_hash=hash_password(password),
                full_name=username,
                role="admin",
                active=True,
            )
            session.add(user)
            session.commit()
        elif not verify_password(user.password_hash, password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid credentials",
            )
        elif not user.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="account disabled",
            )
        token = create_access_token(user.id, user.username, user.role)
        _set_session_cookie(response, token)
    finally:
        session.close()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, request: Request) -> None:
    """Clear the session cookie."""
    _verify_csrf(request)
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