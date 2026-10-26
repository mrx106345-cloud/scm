"""Outbox export service (Part G3, P3-05): the ``outbox.write`` tool.

Creates XLSX/CSV/TXT export files for approved recommendations under
``settings.outbox_dir``. Filenames are system-generated only
(``PO_<display_id>_<timestamp>.{ext}``); every string cell is run through the
formula-injection guard (sanitize_export_cell) and every write/download is
audited. Pure filesystem+DB logic: no LLM, no outbound calls.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.csv_excel import sanitize_export_cell
from app.core.audit import append_entry
from app.db.models import OutboxFile, Recommendation

FileType = Literal["xlsx", "csv", "txt"]

_MEDIA_TYPE: dict[FileType, str] = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "txt": "text/plain",
}


def _filename(display_id: int, file_type: FileType, stamp: str) -> str:
    """System-generated outbox filename: PO_<display_id>_<timestamp>.{ext}."""
    return f"PO_{display_id}_{stamp}.{file_type}"


def _rec_rows(rec: Recommendation) -> list[dict[str, str]]:
    """One row per recommendation: base fields plus the effective payload.

    The effective payload is the human-edited payload when the planner used
    edit_approve, otherwise the original computed payload — the export must
    always reflect what was approved, never the pre-edit numbers.
    """
    raw = rec.edited_payload or rec.payload or "{}"
    payload: object = json.loads(raw)
    row: dict[str, str] = {
        "recommendation_id": rec.id,
        "display_id": str(rec.display_id),
        "action_type": rec.action_type,
        "status": rec.status,
        "decided_at": rec.decided_at.isoformat() if rec.decided_at else "",
        "decided_by": rec.decided_by or "",
        "created_at": rec.created_at.isoformat() if rec.created_at else "",
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            row[str(key)] = "" if value is None else str(value)
    return [row]


def _sanitize_row(row: dict[str, str]) -> dict[str, str]:
    """Formula-injection guard on every cell (security-guardrails CSV/Excel rule)."""
    return {key: sanitize_export_cell(value) for key, value in row.items()}


def _write_file(path: Path, file_type: FileType, rows: list[dict[str, str]]) -> None:
    if not rows:
        rows = [{}]
    headers = list(rows[0].keys())
    clean = [_sanitize_row(row) for row in rows]
    if file_type == "csv":
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in clean:
                writer.writerow(row)
    elif file_type == "txt":
        lines = [",".join(headers)]
        for row in clean:
            lines.append(",".join(row.get(header, "") for header in headers))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:  # xlsx
        wb = Workbook()
        ws = wb.active
        ws.title = "Export"
        ws.append(headers)
        for row in clean:
            ws.append([row.get(header, "") for header in headers])
        wb.save(path)


def write_export(
    session: Session,
    rec_id: str,
    file_type: FileType = "xlsx",
    actor_id: str | None = None,
    actor_role: str | None = None,
    now: datetime | None = None,
) -> OutboxFile:
    """Create an export file for an approved recommendation (outbox.write tool).

    Requires the recommendation to be ``approved`` (matching the
    ``actions.execute`` gate: write-back only on approved status). Writes the
    file under settings.outbox_dir, records an OutboxFile row, and audits
    ``outbox.export``. Returns the created OutboxFile.
    """
    now = now or datetime.now(UTC)
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise FileNotFoundError(f"recommendation {rec_id} not found")
    if rec.status != "approved":
        raise ValueError(
            f"recommendation {rec_id} is {rec.status}, not approved; "
            "outbox export requires an approved recommendation"
        )

    outbox_dir = Path(settings.outbox_dir)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    filename = _filename(rec.display_id, file_type, stamp)
    path = outbox_dir / filename

    _write_file(path, file_type, _rec_rows(rec))

    ofile = OutboxFile(
        filename=filename,
        file_type=file_type,
        recommendation_id=rec.id,
        path=str(path),
        size_bytes=path.stat().st_size,
    )
    session.add(ofile)
    session.flush()
    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type="outbox.export",
        entity_type="outbox_file",
        entity_id=ofile.id,
        payload={
            "file_type": file_type,
            "filename": filename,
            "recommendation_id": rec.id,
            "size_bytes": ofile.size_bytes,
        },
    )
    session.flush()
    return ofile


def list_outbox_files(session: Session) -> list[OutboxFile]:
    """List outbox files, newest first."""
    stmt = select(OutboxFile).order_by(OutboxFile.created_at.desc(), OutboxFile.id)
    return list(session.scalars(stmt))


def get_outbox_file(session: Session, file_id: str) -> OutboxFile | None:
    """Return the outbox file row for file_id, or None."""
    return session.get(OutboxFile, file_id)


def append_download_audit(
    session: Session,
    *,
    actor_id: str | None,
    file_id: str,
    filename: str,
) -> None:
    """Audit an outbox file download (append-only)."""
    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type="outbox.download",
        entity_type="outbox_file",
        entity_id=file_id,
        payload={"filename": filename},
    )


def media_type(file_type: str) -> str:
    """HTTP media type for an outbox file type (DB check-constrains the type)."""
    return _MEDIA_TYPE[cast(FileType, file_type)]
