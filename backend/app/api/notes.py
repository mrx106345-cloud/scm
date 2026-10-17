"""Notes inbox endpoints (api-spec A9, P3-06).

Thin routes: logic lives in app/connectors/notes.py. The acting user is resolved
via the get_current_user dependency (P1-11 real auth); the route layer enforces
roles and audits confirm/dismiss regardless.

Extraction output is a suggestion and never changes calculations before a
Planner confirms.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.connectors import notes as notes_service
from app.core.dependencies import get_current_user
from app.db.models import NoteInbox
from app.db.session import SessionLocal
from app.llm.extract import is_suspicious

router = APIRouter(prefix="/api/v1")


class NoteInRequest(BaseModel):
    """One supplier notice pasted by a user (stored as untrusted text)."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: str | None = None
    raw_text: str = Field(min_length=1, max_length=notes_service.MAX_RAW_TEXT)


class NoteOut(BaseModel):
    """One inbox note with its LLM extraction suggestion."""

    model_config = ConfigDict(extra="forbid")

    id: str
    supplier_id: str | None = None
    raw_text: str | None = None
    extracted: dict[str, object] | None = None
    status: str
    received_at: str | None = None
    suspicious: bool = False


class ConfirmRequest(BaseModel):
    """Human-confirmed values for a note (planner only)."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: str = Field(min_length=1)
    new_delay_days: int = Field(ge=0)
    affected_item_ids: list[str] = Field(default_factory=list)


class ConfirmResponse(BaseModel):
    """Result of confirming a note."""

    model_config = ConfigDict(extra="forbid")

    note: NoteOut
    confirmed: dict[str, object]


class DismissResponse(BaseModel):
    """Result of dismissing a note."""

    model_config = ConfigDict(extra="forbid")

    note: NoteOut


def _require(role: str, allowed: tuple[str, ...]) -> None:
    if role not in allowed:
        raise HTTPException(status_code=403, detail="forbidden")


def _out(note: NoteInbox) -> NoteOut:
    """Serialize a note row; include the caller's own raw text back."""
    extracted: dict[str, object] | None = None
    if note.extracted is not None:
        try:
            extracted = json.loads(note.extracted)
        except (ValueError, TypeError):
            extracted = None
    return NoteOut(
        id=note.id,
        supplier_id=note.supplier_id,
        raw_text=note.raw_text,
        extracted=extracted,
        status=note.status,
        received_at=(note.received_at.isoformat() if note.received_at else None),
        suspicious=is_suspicious(note.raw_text),
    )


def _handle_note_error(exc: notes_service.NoteError) -> HTTPException:
    msg = str(exc)
    if "not found" in msg:
        return HTTPException(status_code=404, detail=msg)
    if "only new" in msg or "already" in msg:
        return HTTPException(status_code=409, detail=msg)
    return HTTPException(status_code=400, detail=msg)


@router.post(
    "/notes",
    status_code=status.HTTP_201_CREATED,
    response_model=NoteOut,
)
def receive_note(
    body: NoteInRequest,
    user: dict = Depends(get_current_user),  # noqa: B008
) -> NoteOut:
    """Receive one supplier notice; stored as untrusted text, status new."""
    role = user.get("role") or "viewer"
    _require(role, ("planner", "purchaser"))
    session = SessionLocal()
    try:
        note = notes_service.create_note(
            session,
            raw_text=body.raw_text,
            supplier_id=body.supplier_id,
            actor_id=user.get("id"),
            actor_role=role,
        )
        session.commit()
        return _out(note)
    except notes_service.NoteError as exc:
        raise _handle_note_error(exc) from exc
    finally:
        session.close()


@router.get("/notes", response_model=list[NoteOut])
def list_notes(user: dict = Depends(get_current_user)) -> list[NoteOut]:  # noqa: B008
    """List inboxed notes, newest first, with status and extraction suggestion."""
    role = user.get("role") or "viewer"
    _require(role, ("planner", "purchaser"))
    session = SessionLocal()
    try:
        notes = notes_service.list_notes(session)
        return [_out(n) for n in notes]
    finally:
        session.close()


@router.post("/notes/{note_id}/confirm", response_model=ConfirmResponse)
def confirm_note(
    note_id: str,
    body: ConfirmRequest,
    user: dict = Depends(get_current_user),  # noqa: B008
) -> ConfirmResponse:
    """Planner confirms a note: only the human-supplied values are applied."""
    role = user.get("role") or "viewer"
    _require(role, ("planner",))
    session = SessionLocal()
    try:
        try:
            note = notes_service.confirm_note(
                session,
                note_id,
                supplier_id=body.supplier_id,
                new_delay_days=body.new_delay_days,
                affected_item_ids=body.affected_item_ids,
                actor_id=user.get("id"),
            )
            session.commit()
        except notes_service.NoteError as exc:
            raise _handle_note_error(exc) from exc
        return ConfirmResponse(
            note=_out(note),
            confirmed={
                "supplier_id": body.supplier_id,
                "new_delay_days": body.new_delay_days,
                "affected_item_ids": body.affected_item_ids,
            },
        )
    finally:
        session.close()


@router.post("/notes/{note_id}/dismiss", response_model=DismissResponse)
def dismiss_note(
    note_id: str,
    user: dict = Depends(get_current_user),  # noqa: B008
) -> DismissResponse:
    """Dismiss a note (planner or purchaser)."""
    role = user.get("role") or "viewer"
    _require(role, ("planner", "purchaser"))
    session = SessionLocal()
    try:
        try:
            note = notes_service.dismiss_note(session, note_id, actor_id=user.get("id"))
            session.commit()
        except notes_service.NoteError as exc:
            raise _handle_note_error(exc) from exc
        return DismissResponse(note=_out(note))
    finally:
        session.close()
