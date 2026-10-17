# mypy: ignore-errors
"""Phase 3 tables: purchase_orders, po_lines, receipts, supplier_metrics, shipments.

Revision ID: 0002_phase3
Revises: 0001_initial
Portable DDL only (Postgres prod / SQLite dev+test).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_phase3"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("po_number", sa.String(64), unique=True, nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("order_date", sa.DateTime, nullable=False),
        sa.Column("promised_date", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.CheckConstraint(
            "status IN ('open','partial','closed','cancelled')", name="ck_po_status"
        ),
    )
    op.create_index("ix_po_supplier", "purchase_orders", ["supplier_id"])
    op.create_index("ix_po_site", "purchase_orders", ["site_id"])
    op.create_index("ix_po_order_date", "purchase_orders", ["order_date"])
    op.create_table(
        "po_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("po_id", sa.String(36), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty_ordered", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("qty_received", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=True),
    )
    op.create_index("ix_poline_po", "po_lines", ["po_id"])
    op.create_index("ix_poline_item", "po_lines", ["item_id"])
    op.create_table(
        "receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("po_line_id", sa.String(36), sa.ForeignKey("po_lines.id"), nullable=False),
        sa.Column("receipt_date", sa.DateTime, nullable=False),
        sa.Column("qty", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_receipt_line", "receipts", ["po_line_id"])
    op.create_index("ix_receipt_date", "receipts", ["receipt_date"])
    op.create_table(
        "supplier_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("mean_lt_recent", sa.Numeric(10, 3), nullable=True),
        sa.Column("mean_lt_prior", sa.Numeric(10, 3), nullable=True),
        sa.Column("drift_pct", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("on_time_rate", sa.Numeric(10, 4), nullable=False, server_default="1"),
        sa.Column("dependency_share", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("risk_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("trend_flag", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("details", sa.Text, nullable=True),
    )
    op.create_index("ix_supmetrics_supplier", "supplier_metrics", ["supplier_id"])
    op.create_index("ix_supmetrics_computed", "supplier_metrics", ["computed_at"])
    op.create_table(
        "shipments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("po_id", sa.String(36), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("reference", sa.String(128), nullable=False, server_default=""),
        sa.Column("carrier", sa.String(128), nullable=False, server_default=""),
        sa.Column("origin", sa.String(128), nullable=False, server_default=""),
        sa.Column("destination", sa.String(128), nullable=False, server_default=""),
        sa.Column("ship_date", sa.DateTime, nullable=True),
        sa.Column("eta", sa.DateTime, nullable=True),
        sa.Column("actual_arrival", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.CheckConstraint(
            "status IN ('open','in_transit','arrived','delayed','cancelled')",
            name="ck_ship_status",
        ),
    )
    op.create_index("ix_ship_po", "shipments", ["po_id"])
    op.create_index("ix_ship_eta", "shipments", ["eta"])


def downgrade() -> None:
    op.drop_index("ix_ship_eta", table_name="shipments")
    op.drop_index("ix_ship_po", table_name="shipments")
    op.drop_table("shipments")
    op.drop_index("ix_supmetrics_computed", table_name="supplier_metrics")
    op.drop_index("ix_supmetrics_supplier", table_name="supplier_metrics")
    op.drop_table("supplier_metrics")
    op.drop_index("ix_receipt_date", table_name="receipts")
    op.drop_index("ix_receipt_line", table_name="receipts")
    op.drop_table("receipts")
    op.drop_index("ix_poline_item", table_name="po_lines")
    op.drop_index("ix_poline_po", table_name="po_lines")
    op.drop_table("po_lines")
    op.drop_index("ix_po_order_date", table_name="purchase_orders")
    op.drop_index("ix_po_site", table_name="purchase_orders")
    op.drop_index("ix_po_supplier", table_name="purchase_orders")
    op.drop_table("purchase_orders")
