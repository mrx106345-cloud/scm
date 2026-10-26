"""SQLAlchemy 2.x typed models. Part C2 of DEVELOPMENT_SPEC."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> str:
    """Return a new UUID string PK."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base for all models."""


class User(Base):
    """App user with role-based access."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("role IN ('admin','planner','purchaser','viewer')", name="ck_users_role"),
    )


class Setting(Base):
    """Key-value settings store."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Site(Base):
    """Physical site / plant."""

    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class Supplier(Base):
    """Supplier master."""

    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_lead_time_days: Mapped[int | None] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Item(Base):
    """Item master. Money NUMERIC(18,2) per spec C1."""

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    uom: Mapped[str] = mapped_column(String(16), nullable=False, default="EA")
    unit_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    criticality: Mapped[str] = mapped_column(String(1), nullable=False, default="C")
    moq: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=1)
    lot_multiple: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=1)
    stockout_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    service_level: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (CheckConstraint("criticality IN ('A','B','C')", name="ck_items_crit"),)


class Alert(Base):
    """Risk alert with dedupe key."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_loss: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    score: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    dedupe_key: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    __table_args__ = (
        CheckConstraint("severity IN ('critical','high','medium','low')", name="ck_alerts_sev"),
        CheckConstraint(
            "status IN ('open','acknowledged','resolved','expired')", name="ck_alerts_st"
        ),
    )


class PurchaseOrder(Base):
    """Purchase order header (spec Part C2)."""

    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    po_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    promised_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")

    __table_args__ = (
        CheckConstraint("status IN ('open','partial','closed','cancelled')", name="ck_po_status"),
    )


class PoLine(Base):
    """Purchase order line."""

    __tablename__ = "po_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    po_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), nullable=False)
    qty_ordered: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    qty_received: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)


class Receipt(Base):
    """Goods receipt against a PO line."""

    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    po_line_id: Mapped[str] = mapped_column(ForeignKey("po_lines.id"), nullable=False)
    receipt_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)


class SupplierMetrics(Base):
    """Computed supplier risk metrics (Part F3). One row per computed_at."""

    __tablename__ = "supplier_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    mean_lt_recent: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    mean_lt_prior: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    drift_pct: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    on_time_rate: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=1)
    dependency_share: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    risk_score: Mapped[int] = mapped_column(nullable=False, default=0)
    trend_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON payload


class Shipment(Base):
    """Inbound shipment for logistics tracking (spec Part F3)."""

    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    po_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    carrier: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    destination: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    ship_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    eta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','in_transit','arrived','delayed','cancelled')",
            name="ck_ship_status",
        ),
    )


class AuditLog(Base):
    """Append-only hash-chained audit log (Part C3)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


class Recommendation(Base):
    """A pending/approved action recommended from an alert (spec Part F4, A5).

    One row per recommended action. display_id is a human-readable sequence
    number used in the UI and outbox file names.
    """

    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    display_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON payload
    est_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    est_benefit: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    benefit_label: Mapped[str] = mapped_column(String(16), nullable=False, default="estimate")
    autonomy_level: Mapped[int] = mapped_column(nullable=False, default=2)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    edited_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('create_draft_po','raise_reorder_request','draft_supplier_message')",
            name="ck_rec_action_type",
        ),
        CheckConstraint(
            "status IN ('pending','approved','rejected','executed','failed','cancelled')",
            name="ck_rec_status",
        ),
    )


class OutboxFile(Base):
    """Generated export file for an approved recommendation (Part G3, P3-05).

    One row per outbox file stored under settings.outbox_dir. Filenames are
    system-generated only (PO_<display_id>_<timestamp>.{ext}); paths are never
    derived from user input.
    """

    __tablename__ = "outbox_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id"), nullable=True, index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("file_type IN ('xlsx','csv','txt')", name="ck_outbox_file_type"),
    )


class NoteInbox(Base):
    """One inboxed supplier notice awaiting human confirmation (Part H5, P3-06).

    raw_text is untrusted user data stored as received. extracted holds the LLM
    suggestion only and never changes calculations until a Planner confirms via
    the API. status is new -> confirmed/dismissed; both are terminal in this
    phase (no column exists for confirmed values beyond supplier_id, per Part
    C2 schema; confirmed new_delay_days/affected_items are recorded in the
    audit payload only).
    """

    __tablename__ = "notes_inbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=True, index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON text
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('new','confirmed','dismissed')", name="ck_note_status"),
    )
