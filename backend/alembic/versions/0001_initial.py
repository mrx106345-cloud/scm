# mypy: ignore-errors
"""Initial schema: users, settings, sites, suppliers, items, alerts, audit_log.

Revision ID: 0001_initial
Revises: None
Alembic runs on PostgreSQL (prod) and SQLite (dev/test); no vendor SQL here.
The audit append-only trigger/rule is Postgres-side (deploy/linux) + a SQLite
trigger in tests; this migration only creates tables + indexes.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default="1"),
        sa.CheckConstraint(
            "role IN ('admin','planner','purchaser','viewer')", name="ck_users_role"
        ),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "sites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
    )
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("contract_lead_time_days", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default="1"),
    )
    op.create_table(
        "items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sku", sa.String(64), unique=True, nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("uom", sa.String(16), nullable=False, server_default="EA"),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("criticality", sa.String(1), nullable=False, server_default="C"),
        sa.Column("moq", sa.Numeric(18, 2), nullable=False, server_default="1"),
        sa.Column("lot_multiple", sa.Numeric(18, 2), nullable=False, server_default="1"),
        sa.Column("stockout_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("service_level", sa.Numeric(5, 4), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default="1"),
        sa.CheckConstraint("criticality IN ('A','B','C')", name="ck_items_crit"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("expected_loss", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("score", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("dedupe_key", sa.String(256), nullable=False, server_default=""),
        sa.CheckConstraint("severity IN ('critical','high','medium','low')", name="ck_alerts_sev"),
        sa.CheckConstraint(
            "status IN ('open','acknowledged','resolved','expired')", name="ck_alerts_st"
        ),
    )
    op.create_index("ix_alerts_item", "alerts", ["item_id"])
    op.create_index("ix_alerts_site", "alerts", ["site_id"])
    op.create_index("ix_alerts_dedupe", "alerts", ["dedupe_key"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text, nullable=True),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.CheckConstraint("actor_type IN ('user','agent','system')", name="ck_audit_actor"),
    )
    op.create_index("ix_audit_ts", "audit_log", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_audit_ts", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_alerts_dedupe", table_name="alerts")
    op.drop_index("ix_alerts_site", table_name="alerts")
    op.drop_index("ix_alerts_item", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("items")
    op.drop_table("suppliers")
    op.drop_table("sites")
    op.drop_table("settings")
    op.drop_table("users")
