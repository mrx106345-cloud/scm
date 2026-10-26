"""Notes inbox service (Part H5, P3-06): receive supplier notices, extract an
LLM suggestion, and require human confirmation before anything is applied.

raw_text is stored unmodified as untrusted data (status ``new``). The LLM
extraction in ``extracted`` is a suggestion only and never changes
calculations; confirmation/dismissal are separate, audited, role-gated API
actions. Every state change writes a hash-chained audit entry.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import append_entry
from app.db.models import NoteInbox
from app.llm.backends import LLMBackend, MockBackend
from app.llm.extract import extract_notice, is_suspicious

MAX_RAW_TEXT = 8000  # api-spec A9: max 8,000 characters per note


class NoteError(ValueError):
    """Raised for invalid note operations (route layer maps to 400/404/409)."""


def create_note(
    session: Session,
    *,
    raw_text: str,
    supplier_id: str | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
    backend: LLMBackend | None = None,
    now: datetime | None = None,
) -> NoteInbox:
    """Receive one supplier notice.

    Stores the raw text unmodified with status ``new``, asks the LLM for an
    extraction suggestion (suspicious input is never sent to the model), and
    audits ``notes.receive``. The suggestion is never auto-applied.
    Returns the created NoteInbox.
    """
    if not raw_text or not raw_text.strip():
        raise NoteError("raw_text is required")
    if len(raw_text) > MAX_RAW_TEXT:
        raise NoteError(f"raw_text exceeds {MAX_RAW_TEXT} characters")

    backend = backend or MockBackend()
    suspicious = is_suspicious(raw_text)
    extraction: dict[str, object] | None = None
    if not suspicious:
        try:
            extraction = extract_notice(raw_text, backend)
        except Exception:  # LLM failure must not lose the notice
            extraction = None

    now = now or datetime.now(UTC)
    note = NoteInbox(
        supplier_id=supplier_id,
        raw_text=raw_text,
        received_at=now,
        extracted=(json.dumps(extraction, sort_keys=True) if extraction is not None else None),
        status="new",
    )
    session.add(note)
    session.flush()
    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type="notes.receive",
        entity_type="note",
        entity_id=note.id,
        payload={
            "supplier_id": supplier_id,
            "suspicious": suspicious,
            "extracted": extraction is not None,
            "raw_text_chars": len(raw_text),
        },
    )
    session.flush()
    return note


def list_notes(session: Session) -> list[NoteInbox]:
    """List notes, newest first."""
    stmt = select(NoteInbox).order_by(NoteInbox.received_at.desc(), NoteInbox.id.desc())
    return list(session.scalars(stmt))


def get_note(session: Session, note_id: str) -> NoteInbox | None:
    """Return the note row for note_id, or None."""
    return session.get(NoteInbox, note_id)


def confirm_note(
    session: Session,
    note_id: str,
    *,
    supplier_id: str,
    new_delay_days: int,
    affected_item_ids: list[str] | None = None,
    actor_id: str | None = None,
) -> NoteInbox:
    affected_item_ids = affected_item_ids or []
    """Planner-confirmed note.

    Requires status ``new`` (terminal otherwise). Writes only the
    human-confirmed supplier_id and status to the row; the confirmed
    new_delay_days/affected_item_ids and the LLM suggestion are recorded in
    the audit payload. Audits ``notes.confirm``. Returns the updated note.
    """
    note = get_note(session, note_id)
    if note is None:
        raise NoteError(f"note {note_id} not found")
    if note.status != "new":
        raise NoteError(f"note {note_id} is {note.status}; only new notes can be confirmed")
    if not supplier_id or not str(supplier_id).strip():
        raise NoteError("supplier_id is required")
    if not _is_int(new_delay_days) or new_delay_days < 0:
        raise NoteError("new_delay_days must be a non-negative integer")
    if not isinstance(affected_item_ids, list) or not all(
        isinstance(it, str) for it in affected_item_ids
    ):
        raise NoteError("affected_item_ids must be a list of strings")

    note.supplier_id = str(supplier_id)
    note.status = "confirmed"
    session.add(note)
    session.flush()
    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type="notes.confirm",
        entity_type="note",
        entity_id=note.id,
        payload={
            "supplier_id": note.supplier_id,
            "new_delay_days": new_delay_days,
            "affected_item_ids": affected_item_ids,
            "suggestion": note.extracted,
        },
    )
    session.flush()
    return note


def dismiss_note(
    session: Session,
    note_id: str,
    *,
    actor_id: str | None = None,
) -> NoteInbox:
    """Dismiss a note (planner or purchaser). Requires status ``new``."""
    note = get_note(session, note_id)
    if note is None:
        raise NoteError(f"note {note_id} not found")
    if note.status != "new":
        raise NoteError(f"note {note_id} is {note.status}; only new notes can be dismissed")
    note.status = "dismissed"
    session.add(note)
    session.flush()
    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type="notes.dismiss",
        entity_type="note",
        entity_id=note.id,
        payload={"supplier_id": note.supplier_id},
    )
    session.flush()
    return note


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
