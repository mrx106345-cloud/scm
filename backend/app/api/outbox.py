"""Outbox export list + download endpoints (api-spec A5/A14, P3-05).

Thin routes: logic lives in app/connectors/outbox.py. The acting user is resolved
via the get_current_user dependency (P1-11 real auth); the route layer enforces
roles and audits downloads regardless.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from app.config import settings
from app.connectors import outbox as outbox_service
from app.core.dependencies import get_current_user
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")


class OutboxFileOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str
    created_at: str | None = None
    recommendation_id: str | None = None


def _require_planner_or_purchaser(role: str) -> None:
    """admin/planner/purchaser may list and download outbox files; viewer denied."""
    if role not in ("admin", "planner", "purchaser"):
        raise HTTPException(status_code=403, detail="forbidden")


def _is_inside(path: Path, root: Path) -> bool:
    """True if path resolves underneath root (path-traversal guard)."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


@router.get("/outbox", response_model=list[OutboxFileOut])
def list_outbox(
    user: dict[str, str | None] = Depends(get_current_user),  # noqa: B008
) -> list[OutboxFileOut]:
    """List generated outbox files (name, type, created_at, recommendation_id)."""
    role = user.get("role") or ""
    _require_planner_or_purchaser(role)
    session = SessionLocal()
    try:
        files = outbox_service.list_outbox_files(session)
        return [
            OutboxFileOut(
                id=f.id,
                name=f.filename,
                type=f.file_type,
                created_at=f.created_at.isoformat() if f.created_at else None,
                recommendation_id=f.recommendation_id,
            )
            for f in files
        ]
    finally:
        session.close()


@router.get("/outbox/{file_id}/download")
def download_outbox(
    file_id: str,
    user: dict[str, str | None] = Depends(get_current_user),  # noqa: B008
) -> FileResponse:
    """Download an outbox file; every download is audited."""
    role = user.get("role") or ""
    _require_planner_or_purchaser(role)
    session = SessionLocal()
    try:
        f = outbox_service.get_outbox_file(session, file_id)
        if f is None:
            raise HTTPException(status_code=404, detail="outbox file not found")
        path = Path(f.path)
        if not path.is_file() or not _is_inside(path, Path(settings.outbox_dir)):
            raise HTTPException(status_code=404, detail="export file missing")
        outbox_service.append_download_audit(
            session, actor_id=user.get("id"), file_id=f.id, filename=f.filename
        )
        session.commit()
        return FileResponse(
            path=path,
            filename=f.filename,
            media_type=outbox_service.media_type(f.file_type),
        )
    finally:
        session.close()
