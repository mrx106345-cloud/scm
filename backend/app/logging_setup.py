"""Structured JSON logging. No secrets or C3 values may be logged.

Use the redaction helper for connector-derived content.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_SECRET_KEYS = {"password", "secret", "credential", "token", "key", "passphrase"}


def redact(mapping: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with secret-looking keys masked."""
    out: dict[str, Any] = {}
    for k, v in mapping.items():
        if any(s in k.lower() for s in _SECRET_KEYS):
            out[k] = "***"
        else:
            out[k] = v
    return out


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog JSON output to stdout."""
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
