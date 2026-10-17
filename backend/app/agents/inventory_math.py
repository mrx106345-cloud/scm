"""Deterministic inventory math (Parts E3/E4 of DEVELOPMENT_SPEC).

Pure functions only. Money uses Decimal. This module is the skeleton for
P1-01; full formulas land in P1-08 with golden tests from evaluation-dataset.json.
"""

from __future__ import annotations

from decimal import Decimal


def days_of_cover(on_hand: Decimal, allocated: Decimal, avg_daily_demand: Decimal) -> Decimal:
    """Days of cover = (on_hand - allocated) / d. Returns 0 when d <= 0."""
    if avg_daily_demand <= 0:
        return Decimal("0")
    return (on_hand - allocated) / avg_daily_demand
