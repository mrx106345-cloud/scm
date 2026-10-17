"""Tamper-evident audit log (Part C3).

hash = sha256(prev_hash || canonical_json({ts, actor_type, actor_id,
event_type, entity_type, entity_id, payload})). Genesis prev_hash = 64 zeros.
Never store secrets in payloads.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditLog

GENESIS_HASH = "0" * 64


def utc_now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(UTC).isoformat()


def canonical_json(data: dict[str, object]) -> str:
    """Serialize deterministically for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def chain_hash(prev_hash: str, entry: dict[str, object]) -> str:
    """Compute the audit row hash from prev_hash + canonical entry JSON."""
    body = prev_hash + canonical_json(entry)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def append_entry(
    session: Session,
    actor_type: str,
    actor_id: str | None,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, object] | str,
) -> str:
    """Append one tamper-evident audit row and return its hash."""
    prev = session.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()))
    if prev is None:
        prev = GENESIS_HASH
    now = datetime.now(UTC)
    entry: dict[str, object] = {
        "ts": now.isoformat(),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload,
    }
    h = chain_hash(prev, entry)
    stored_payload = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    session.add(
        AuditLog(
            ts=now,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=stored_payload,
            prev_hash=prev,
            hash=h,
        )
    )
    return h
