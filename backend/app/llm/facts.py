"""Explainer facts builders (Part H2). Minimal computed facts only.

The facts object carries C3 business data but no raw tables, credentials,
documents, or other users' data — and only what was computed by the
deterministic pipeline, never LLM output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class AlertExplanationFacts:
    """Computed values an explanation may mention (spec Part H2)."""

    item_name: str
    site: str
    on_hand: float
    days_to_stockout: float
    supplier_name: str
    lead_time_days: float
    stockout_probability_pct: float
    expected_loss: str  # Decimal string, 2 dp
    suggested_qty: float
    extra_cost: str  # Decimal string, 2 dp
    severity: str
    alert_type: str

    def to_json_dict(self) -> dict[str, object]:
        """Facts payload for the prompt and the number validator."""
        return asdict(self)
