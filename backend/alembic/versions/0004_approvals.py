# mypy: ignore-errors
"""Phase 3: approval decision columns on recommendations (P3-04).

Revision ID: 0004_approvals
Revises: 0003_recommendations
Portable DDL only (Postgres prod / SQLite dev+test).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_approvals"
down_revision = "0003_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("decided_at", sa.DateTime, nullable=True))
    op.add_column("recommendations", sa.Column("decided_by", sa.String(64), nullable=True))
    op.add_column("recommendations", sa.Column("edited_payload", sa.Text, nullable=True))
    op.add_column("recommendations", sa.Column("decision_comment", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "decision_comment")
    op.drop_column("recommendations", "edited_payload")
    op.drop_column("recommendations", "decided_by")
    op.drop_column("recommendations", "decided_at")
