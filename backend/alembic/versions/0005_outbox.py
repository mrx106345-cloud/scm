# mypy: ignore-errors
"""Outbox files table for export generation (P3-05).

Revision ID: 0005_outbox
Revises: 0004_approvals
Portable DDL only (Postgres prod / SQLite dev+test).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_outbox"
down_revision = "0004_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_files",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("file_type", sa.String(8), nullable=False),
        sa.Column(
            "recommendation_id",
            sa.String(36),
            sa.ForeignKey("recommendations.id"),
            nullable=True,
        ),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("file_type IN ('xlsx','csv','txt')", name="ck_outbox_file_type"),
    )
    op.create_index("ix_outbox_files_recommendation_id", "outbox_files", ["recommendation_id"])


def downgrade() -> None:
    op.drop_index("ix_outbox_files_recommendation_id", table_name="outbox_files")
    op.drop_table("outbox_files")
