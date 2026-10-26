"""Inventory parameters + stockout probability + expected loss (Parts E3/E4).

All demand math uses weekly buckets in the pipeline; these are pure functions
operating on daily rates. Money as float here mirrors NUMERIC(18,2); API layer
serializes Decimal strings per api-spec.
"""

from __future__ import annotations

import math
from statistics import NormalDist

_NORM = NormalDist()


def z_for_service_level(sl: float) -> float:
    """Inverse normal CDF for a service level in (0,1)."""
    if not 0 < sl < 1:
        raise ValueError("service level must be in (0,1)")
    return _NORM.inv_cdf(sl)


def safety_stock(
    z: float, lead_time_days: float, sigma_d: float, d: float, sigma_lt: float
) -> float:
    """SS = z * sqrt(LT*sigma_d^2 + d^2*sigma_LT^2)."""
    var = lead_time_days * sigma_d**2 + d**2 * sigma_lt**2
    return z * math.sqrt(max(0.0, var))


def reorder_point(d: float, lead_time_days: float, ss: float) -> float:
    """ROP = d * LT + SS."""
    return d * lead_time_days + ss


def order_qty(moq: float, lot_multiple: float, target_cover_days: float, d: float) -> float:
    """Q = max(MOQ, cover*d) rounded UP to lot_multiple."""
    raw = max(moq, target_cover_days * d)
    if lot_multiple <= 0:
        return raw
    return math.ceil(raw / lot_multiple) * lot_multiple


def stockout_probability(available: float, mu: float, sd: float) -> float:
    """P(stockout) = 1 - CDF((A-mu)/sd). Step fn when sd == 0."""
    if sd <= 0:
        return 1.0 if available < mu else 0.0
    z_a = (available - mu) / sd
    return 1.0 - _NORM.cdf(z_a)


def expected_shortage(available: float, mu: float, sd: float) -> float:
    """Normal loss function ES = sd*(pdf(z_a) - z_a*(1-cdf(z_a)))."""
    if sd <= 0:
        return max(0.0, mu - available)
    z_a = (available - mu) / sd
    return sd * (_NORM.pdf(z_a) - z_a * (1.0 - _NORM.cdf(z_a)))


def days_of_cover_float(on_hand: float, allocated: float, d: float) -> float | None:
    """DOC = (on_hand - allocated) / d; None when demand is zero.

    Per evaluation-dataset.json INV-06 and the golden clarification: a
    zero-demand item has no cover days (null) and must raise no stockout
    alert; only the API caller decides how null is serialized.
    """
    if d <= 0:
        return None
    return (on_hand - allocated) / d
