# mypy: ignore-errors
"""Notes inbox table for supplier notices (P3-06).

Revision ID: 0006_notes
Revises: 0005_outbox
Portable DDL only (Postgres prod / SQLite dev+test).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_notes"
down_revision = "0005_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notes_inbox",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "supplier_id",
            sa.String(36),
            sa.ForeignKey("suppliers.id"),
            nullable=True,
        ),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("extracted", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column(
            "received_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('new','confirmed','dismissed')", name="ck_note_status"),
    )
    op.create_index("ix_notes_inbox_supplier_id", "notes_inbox", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_notes_inbox_supplier_id", table_name="notes_inbox")
    op.drop_table("notes_inbox")
