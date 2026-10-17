# mypy: ignore-errors
"""Phase 3 table: recommendations (P3-03, spec Part F4 / A5).

Revision ID: 0003_recommendations
Revises: 0002_phase3
Portable DDL only (Postgres prod / SQLite dev+test).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_recommendations"
down_revision = "0002_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_id", sa.Integer, nullable=False, unique=True),
        sa.Column("alert_id", sa.String(36), sa.ForeignKey("alerts.id"), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("payload", sa.Text, nullable=True),
        sa.Column("est_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("est_benefit", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "benefit_label", sa.String(16), nullable=False, server_default="estimate"
        ),
        sa.Column("autonomy_level", sa.Integer, nullable=False, server_default="2"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "action_type IN ('create_draft_po','raise_reorder_request','draft_supplier_message')",
            name="ck_rec_action_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','executed','failed','cancelled')",
            name="ck_rec_status",
        ),
    )
    op.create_index("ix_rec_alert", "recommendations", ["alert_id"])
    op.create_index("ix_rec_status", "recommendations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_rec_status", table_name="recommendations")
    op.drop_index("ix_rec_alert", table_name="recommendations")
    op.drop_table("recommendations")
