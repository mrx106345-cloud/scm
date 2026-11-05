"""Connector interface (Part G1, P4-04/P4-06).

Connectors read data into canonical entities and, only if explicitly allowed,
write approved actions back to the source system. A connector never decides
what to write: the action agent supplies an approved recommendation payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class ConnectorError(RuntimeError):
    """Raised when a connector cannot complete a read/write safely."""


@dataclass(frozen=True)
class ConnectorTestResult:
    """Result of a connectivity/credential test (never includes secrets)."""

    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorRunResult:
    """Result of one read run."""

    status: str  # ok | partial | failed
    imported: int = 0
    warnings: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WriteResult:
    """Result of a write-back attempt."""

    ok: bool
    reference: str
    message: str = ""


@runtime_checkable
class Connector(Protocol):
    """Minimal connector contract used by the API and the action agent."""

    type: str

    def test(self) -> ConnectorTestResult:
        """Validate config/credentials without importing data."""

    def run(self, session: Any) -> ConnectorRunResult:
        """Import canonical entities into the database."""

    def write(self, session: Any, payload: dict[str, Any]) -> WriteResult:
        """Write one approved action back to the source system."""
