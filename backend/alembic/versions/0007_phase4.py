# mypy: ignore-errors
"""Phase 4 tables: connectors, actions, data_quality_runs (P4-04..07).

Revision ID: 0007_phase4
Revises: 0006_notes
Portable DDL only (Postgres prod / SQLite dev+test).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_phase4"
down_revision = "0006_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("config_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("write_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("schedule_cron", sa.String(64), nullable=True),
        sa.Column("last_run_at", sa.DateTime, nullable=True),
        sa.Column("last_status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_connector_name"),
        sa.CheckConstraint(
            "type IN ('csv','sql','tally','sap_b1','zoho')", name="ck_connector_type"
        ),
    )

    op.create_table(
        "actions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "recommendation_id",
            sa.String(36),
            sa.ForeignKey("recommendations.id"),
            nullable=False,
        ),
        sa.Column("executed_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("target", sa.String(16), nullable=False),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("target IN ('outbox','connector')", name="ck_action_target"),
        sa.CheckConstraint(
            "status IN ('executed','failed','blocked')", name="ck_action_status"
        ),
    )
    op.create_index("ix_actions_recommendation_id", "actions", ["recommendation_id"])

    op.create_table(
        "data_quality_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("run_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column(
            "connector_id",
            sa.String(36),
            sa.ForeignKey("connectors.id"),
            nullable=True,
        ),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("critical_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("details", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_quality_runs_connector_id", "data_quality_runs", ["connector_id"])
    op.create_index("ix_data_quality_runs_run_at", "data_quality_runs", ["run_at"])


def downgrade() -> None:
    op.drop_index("ix_data_quality_runs_run_at", table_name="data_quality_runs")
    op.drop_index("ix_data_quality_runs_connector_id", table_name="data_quality_runs")
    op.drop_table("data_quality_runs")
    op.drop_index("ix_actions_recommendation_id", table_name="actions")
    op.drop_table("actions")
    op.drop_table("connectors")
