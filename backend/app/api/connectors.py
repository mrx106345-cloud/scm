"""Connector administration API (api-spec A12, P4-04/P4-06/P4-07).

Admin-only. Connector configs are encrypted at rest and **always** returned
masked: secret-looking keys become ``***``. Raw config never reaches a log,
audit payload or HTTP response.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.connectors.base import ConnectorError
from app.connectors.registry import CONNECTOR_TYPES, build_connector, is_write_capable
from app.connectors.sap_b1 import SapError, validate_allowed_host
from app.connectors.zoho import OUTBOUND_WARNING
from app.core.audit import append_entry
from app.core.crypto import CryptoError, decrypt_config, encrypt_config, mask_config
from app.core.dependencies import require_role
from app.db.models import Connector
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")

_ADMIN = require_role("admin")


class ConnectorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    write_enabled: bool = False
    schedule_cron: str | None = Field(default=None, max_length=64)


class ConnectorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] | None = None
    write_enabled: bool | None = None
    schedule_cron: str | None = Field(default=None, max_length=64)


class ConnectorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str
    config: dict[str, Any]
    write_enabled: bool
    schedule_cron: str | None = None
    last_run_at: str | None = None
    last_status: str | None = None
    outbound: bool = False


class ConnectorTestOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str


def _validate(row_type: str, config: dict[str, Any]) -> None:
    """Reject unsupported types and unsafe connector configs."""
    if row_type not in CONNECTOR_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported connector type: {row_type}")
    if row_type == "sap_b1":
        base_url = str(config.get("base_url") or "")
        try:
            validate_allowed_host(base_url, settings.sap_allowed_hosts)
        except SapError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


def _to_out(row: Connector) -> ConnectorOut:
    """Serialize a connector with secrets masked (never raises on bad key)."""
    try:
        config = mask_config(decrypt_config(row.config_encrypted))
    except CryptoError:
        config = {"config": "unreadable"}
    return ConnectorOut(
        id=row.id,
        name=row.name,
        type=row.type,
        config=config,
        write_enabled=row.write_enabled,
        schedule_cron=row.schedule_cron,
        last_run_at=row.last_run_at.isoformat() if row.last_run_at else None,
        last_status=row.last_status,
        outbound=row.type == "zoho",
    )


def _audit(
    session: Any,
    event_type: str,
    connector: Connector,
    actor_id: str | None,
    payload: dict[str, Any],
) -> None:
    append_entry(
        session,
        actor_type="user",
        actor_id=actor_id,
        event_type=event_type,
        entity_type="connector",
        entity_id=connector.id,
        payload=payload,
    )


@router.get("/connectors", response_model=list[ConnectorOut])
def list_connectors(
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> list[ConnectorOut]:
    """List connectors; configs are masked and never include secrets."""
    session = SessionLocal()
    try:
        rows = session.query(Connector).order_by(Connector.name).all()
        return [_to_out(row) for row in rows]
    finally:
        session.close()


@router.post("/connectors", response_model=ConnectorOut, status_code=201)
def create_connector(
    body: ConnectorCreate,
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> ConnectorOut:
    """Register a connector. Config is encrypted immediately."""
    _validate(body.type, body.config)
    if body.write_enabled and not is_write_capable(body.type):
        raise HTTPException(status_code=400, detail=f"{body.type} connectors are read-only")
    if body.write_enabled and body.type == "zoho" and not settings.zoho_enabled:
        raise HTTPException(
            status_code=403,
            detail="zoho is disabled; set SCM_ZOHO_ENABLED=true after owner approval",
        )
    session = SessionLocal()
    try:
        if session.query(Connector).filter(Connector.name == body.name).first() is not None:
            raise HTTPException(status_code=409, detail="connector name already exists")
        row = Connector(
            name=body.name,
            type=body.type,
            config_encrypted=encrypt_config(body.config),
            write_enabled=body.write_enabled,
            schedule_cron=body.schedule_cron,
        )
        session.add(row)
        session.flush()
        _audit(
            session,
            "connector.created",
            row,
            user.get("id"),
            {
                "name": row.name,
                "type": row.type,
                "write_enabled": row.write_enabled,
                "config": mask_config(body.config),
                "outbound_warning": OUTBOUND_WARNING if row.type == "zoho" else None,
            },
        )
        session.commit()
        return _to_out(row)
    finally:
        session.close()


@router.get("/connectors/{connector_id}", response_model=ConnectorOut)
def get_connector(
    connector_id: str,
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> ConnectorOut:
    session = SessionLocal()
    try:
        row = session.get(Connector, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        return _to_out(row)
    finally:
        session.close()


@router.patch("/connectors/{connector_id}", response_model=ConnectorOut)
def update_connector(
    connector_id: str,
    body: ConnectorUpdate,
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> ConnectorOut:
    """Update config/flags; every change is audited with the masked config."""
    session = SessionLocal()
    try:
        row = session.get(Connector, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        if body.config is not None:
            _validate(row.type, body.config)
            row.config_encrypted = encrypt_config(body.config)
        if body.write_enabled is not None:
            if body.write_enabled and not is_write_capable(row.type):
                raise HTTPException(status_code=400, detail=f"{row.type} connectors are read-only")
            if body.write_enabled and row.type == "zoho" and not settings.zoho_enabled:
                raise HTTPException(
                    status_code=403,
                    detail="zoho is disabled; set SCM_ZOHO_ENABLED=true after owner approval",
                )
            row.write_enabled = body.write_enabled
        if body.schedule_cron is not None:
            row.schedule_cron = body.schedule_cron
        _audit(
            session,
            "connector.updated",
            row,
            user.get("id"),
            {
                "name": row.name,
                "type": row.type,
                "write_enabled": row.write_enabled,
                "config": _to_out(row).config,
            },
        )
        session.commit()
        return _to_out(row)
    finally:
        session.close()


@router.post("/connectors/{connector_id}/test", response_model=ConnectorTestOut)
def test_connector(
    connector_id: str,
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> ConnectorTestOut:
    """Run the connector's credential/host check (no data import)."""
    session = SessionLocal()
    try:
        row = session.get(Connector, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        try:
            if row.type == "zoho":
                result = build_connector(row).test()
                ok, message = result.ok, result.message
            else:
                ok, message = True, "config accepted; no live connectivity check for this type"
        except ConnectorError as exc:
            ok, message = False, str(exc)
        _audit(
            session,
            "connector.tested",
            row,
            user.get("id"),
            {"type": row.type, "ok": ok, "message": message},
        )
        session.commit()
        return ConnectorTestOut(ok=ok, message=message)
    finally:
        session.close()


@router.get("/connectors/{connector_id}/outbound-warning")
def outbound_warning(
    connector_id: str,
    user: dict[str, str | None] = Depends(_ADMIN),  # noqa: B008
) -> dict[str, object]:
    """Return the explicit warning shown before enabling an outbound connector."""
    session = SessionLocal()
    try:
        row = session.get(Connector, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        warning = OUTBOUND_WARNING if row.type == "zoho" else "this connector is local-only"
        return {"connector_id": row.id, "outbound": row.type == "zoho", "warning": warning}
    finally:
        session.close()
