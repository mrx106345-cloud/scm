"""Recommendation agent (Part F4, P3-03): draft POs and supplier messages.

Pure computation is separated from the DB runner. All money/quantities are
deterministic; no LLM is involved in generating recommendations or the
supplier message template (I3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, Item, PoLine, PurchaseOrder, Recommendation, Supplier


@dataclass(frozen=True)
class SupplierMessage:
    """Deterministic supplier message (spec I3): subject + body with placeholders filled."""

    subject: str
    body: str


def _round_up_to_lot(qty: float, lot_multiple: float) -> float:
    if lot_multiple and lot_multiple > 0:
        steps = (
            Decimal(str(qty)) / Decimal(str(lot_multiple))
        ).to_integral_value(rounding=ROUND_UP)
        return float(steps * Decimal(str(lot_multiple)))
    return qty


def compute_order_qty(
    item: Item,
    q: float | None = None,
    rop: float | None = None,
    available: float | None = None,
) -> float:
    """Spec F4 order qty: ``max(Q, ROP + Q - A)`` rounded up to the lot multiple.

    When inventory parameters (Q/ROP/available) are not yet available, fall
    back to ``item.moq`` rounded up to the lot multiple.
    """
    lot = float(item.lot_multiple or 1.0)
    if q is None or rop is None or available is None:
        return _round_up_to_lot(float(item.moq), lot)
    return _round_up_to_lot(max(float(q), float(rop) + float(q) - float(available)), lot)


def draft_supplier_message(
    supplier_name: str,
    po_number: str,
    item_sku: str,
    qty: float,
    promised_date: datetime | None,
) -> SupplierMessage:
    """Spec I3: deterministic supplier message asking for a confirmed delivery date."""
    due = promised_date.date().isoformat() if promised_date is not None else "as soon as possible"
    subject = f"Delivery confirmation requested for PO {po_number} ({item_sku})"
    body = (
        f"Dear {supplier_name},\n\n"
        f"Regarding purchase order {po_number} for item {item_sku} "
        f"(quantity {qty}), the promised delivery date of {due} is approaching "
        f"and we have not yet received a confirmed dispatch.\n\n"
        f"Please confirm the expected delivery date for this order at your "
        f"earliest convenience so we can adjust our inbound plan.\n\n"
        f"Thank you.\n"
    )
    return SupplierMessage(subject=subject, body=body)


def _next_display_id(session: Session) -> int:
    row = session.scalar(
        select(Recommendation.display_id).order_by(Recommendation.display_id.desc())
    )
    return (row or 0) + 1


def _existing_pending(session: Session, alert_id: str, action_type: str) -> Recommendation | None:
    return session.scalar(
        select(Recommendation).where(
            Recommendation.alert_id == alert_id,
            Recommendation.action_type == action_type,
            Recommendation.status == "pending",
        )
    )


def create_recommendations(session: Session) -> list[Recommendation]:
    """Generate pending recommendations from open alerts (spec Part F4).

    - ``stockout_risk`` alert -> ``create_draft_po`` (qty per F4 formula).
    - ``supplier_delay`` alert -> ``draft_supplier_message`` (spec I3 template).

    Idempotent: a second run does not duplicate an existing pending
    recommendation for the same alert + action type.
    """
    created: list[Recommendation] = []
    alerts = session.scalars(select(Alert).where(Alert.status == "open")).all()

    for alert in alerts:
        item = session.get(Item, alert.item_id) if alert.item_id else None
        supplier = (
            session.get(Supplier, alert.supplier_id) if alert.supplier_id else None
        )

        if alert.type == "stockout_risk":
            if item is None or supplier is None:
                continue
            if _existing_pending(session, alert.id, "create_draft_po") is not None:
                continue
            qty = compute_order_qty(item)
            unit_price = float(item.unit_cost or 0.0)
            est_cost = round(qty * unit_price, 2)
            payload = {
                "supplier_id": supplier.id,
                "item_id": item.id,
                "qty": qty,
                "unit_price": f"{unit_price:.2f}",
                "need_by_date": None,
            }
            rec = Recommendation(
                display_id=_next_display_id(session),
                alert_id=alert.id,
                action_type="create_draft_po",
                payload=json.dumps(payload),
                est_cost=est_cost,
                est_benefit=float(alert.expected_loss),
                benefit_label="estimate",
                autonomy_level=2,
                status="pending",
            )
            session.add(rec)
            created.append(rec)

        elif alert.type == "supplier_delay":
            if item is None or supplier is None:
                continue
            if _existing_pending(session, alert.id, "draft_supplier_message") is not None:
                continue
            po_line = session.scalar(
                select(PoLine)
                .join(PurchaseOrder, PurchaseOrder.id == PoLine.po_id)
                .where(
                    PoLine.item_id == item.id,
                    PurchaseOrder.supplier_id == supplier.id,
                    PurchaseOrder.status == "open",
                )
                .order_by(PurchaseOrder.order_date.desc())
            )
            po_number = "—"
            promised = None
            if po_line is not None:
                po = session.get(PurchaseOrder, po_line.po_id)
                if po is not None:
                    po_number = po.po_number
                    promised = po.promised_date
            qty = float(po_line.qty_ordered) if po_line is not None else float(item.moq)
            message = draft_supplier_message(supplier.name, po_number, item.sku, qty, promised)
            payload = {
                "supplier_id": supplier.id,
                "item_id": item.id,
                "po_number": po_number,
                "qty": qty,
                "promised_date": promised.isoformat() if promised else None,
                "message_text": message.body,
            }
            rec = Recommendation(
                display_id=_next_display_id(session),
                alert_id=alert.id,
                action_type="draft_supplier_message",
                payload=json.dumps(payload),
                est_cost=None,
                est_benefit=float(alert.expected_loss),
                benefit_label="estimate",
                autonomy_level=2,
                status="pending",
            )
            session.add(rec)
            created.append(rec)

    session.flush()
    return created
