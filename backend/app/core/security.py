"""Auth security: argon2id hashing, lockout, RBAC gate (P1-03).

Passwords: argon2id, min 12 chars. Lockout 5 failures / 15 min.
Sessions: HTTP-only Secure SameSite=Strict cookie + CSRF header (wired in P1-11).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()

# Role rank: higher includes lower. Deny by default.
ROLE_RANK = {"viewer": 0, "purchaser": 1, "planner": 2, "admin": 3}

COMMON_PASSWORDS = {"password1234", "changeme12345", "scmagent1234", "letmein123456"}


def hash_password(password: str) -> str:
    """Hash a password with argon2id. Enforces min length + common list."""
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("password is too common")
    return _ph.hash(password)


def verify_password(hash_: str, password: str) -> bool:
    """Return True when password matches hash, else False."""
    try:
        return _ph.verify(hash_, password)
    except VerifyMismatchError:
        return False


def can_access(user_role: str, minimum_role: str) -> bool:
    """Deny-by-default RBAC check. Unknown roles deny."""
    if user_role not in ROLE_RANK or minimum_role not in ROLE_RANK:
        return False
    if minimum_role in ("public", "any"):
        return True
    return ROLE_RANK[user_role] >= ROLE_RANK[minimum_role]


class LockoutTracker:
    """In-memory login failure tracker with a sliding lockout window."""

    def __init__(self, max_failures: int = 5, window_minutes: int = 15) -> None:
        """Init with failure threshold and the window failures stay counted in."""
        self.max_failures = max_failures
        self.window = timedelta(minutes=window_minutes)
        self._failures: dict[str, list[datetime]] = {}

    def record_failure(self, username: str) -> int:
        """Record a failure; return current count inside the window."""
        now = datetime.now(UTC)
        history = [t for t in self._failures.get(username, []) if now - t < self.window]
        history.append(now)
        self._failures[username] = history
        return len(history)

    def record_success(self, username: str) -> None:
        """Clear failures on success."""
        self._failures.pop(username, None)

    def is_locked(self, username: str) -> bool:
        """Return True when failures inside the window reach the threshold."""
        now = datetime.now(UTC)
        history = [t for t in self._failures.get(username, []) if now - t < self.window]
        if history:
            self._failures[username] = history
        return len(history) >= self.max_failures
