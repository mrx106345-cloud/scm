"""FastAPI dependencies for real authentication (P1-11).

Replaces the temporary X-Acting-Role / X-Acting-User header placeholder.
reads the session cookie, verifies the JWT, and returns the current user.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status

from app.core.session import decode_access_token


def _extract_token(request: Request, session_cookie: str | None) -> str | None:
    """Pull the access token from the HTTP-only session cookie."""
    if session_cookie:
        return session_cookie
    # Fallback: Authorization: Bearer <token> for non-browser clients.
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def get_current_user(
    request: Request,
    session_cookie: Annotated[str | None, Cookie(alias="session")] = None,
) -> dict[str, str | None]:
    """Return the authenticated user {id, username, role} or raise 401."""
    token = _extract_token(request, session_cookie)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "id": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
    }


def require_role(minimum_role: str):
    """Dependency factory: require the caller to have at least minimum_role."""

    def _checker(user: dict[str, str | None] = Depends(get_current_user)) -> dict[str, str | None]:  # noqa: B008
        from app.core.security import can_access

        user_role = user.get("role") or "viewer"
        if not can_access(user_role, minimum_role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _checker