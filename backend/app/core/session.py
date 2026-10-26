"""Session management: JWT access tokens + HTTP-only cookie helpers (P1-11).

Passwords: argon2id (see app/core/security.py).
Sessions: HTTP-only Secure SameSite=Strict cookie + CSRF token on non-GET.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_SUBJECT = "access"  # noqa: S105 — JWT token type, not a password


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token encoding user id, username, role."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.session_idle_minutes))
    to_encode: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": expire,
        "typ": ACCESS_TOKEN_SUBJECT,
    }
    return jwt.encode(to_encode, settings.session_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT access token. Returns payload or None if invalid."""
    try:
        payload: dict[str, Any] = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != ACCESS_TOKEN_SUBJECT:
        return None
    return payload
