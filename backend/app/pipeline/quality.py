"""Data quality checks + score (Part D). Pure functions, no DB.

Score = 100 - 20*min(critical_types,3) - 3*min(warning_types,10). Floor 0.
Gate: any critical check failing for an entity -> agents skip affected items
and a data_quality alert is raised (wired in alert agent P1-09).
"""

from __future__ import annotations

from statistics import median


def mad(values: list[float]) -> float:
    """Median absolute deviation."""
    if not values:
        return 0.0
    m = median(values)
    return median([abs(v - m) for v in values])


CRITICAL = {"missing_required", "negative_stock", "duplicate_keys", "stale_data", "orphan_refs"}


def quality_score(critical_types: int, warning_types: int) -> int:
    """Compute the 0-100 data quality score from distinct check-type counts."""
    score = 100 - 20 * min(critical_types, 3) - 3 * min(warning_types, 10)
    return max(0, score)


def flag_outliers(consumption: list[float]) -> list[int]:
    """Return indexes where qty > median + 8*MAD (flag, do not delete)."""
    if not consumption:
        return []
    m = median(consumption)
    threshold = m + 8 * mad(consumption)
    return [i for i, q in enumerate(consumption) if q > threshold]


def unit_cost_jump(old: float, new: float) -> bool:
    """True when unit_cost changes by more than 10x between loads."""
    if old == 0:
        return new != 0
    if new == 0:
        return True  # a drop to zero is itself a >10x jump, not ZeroDivisionError
    return max(old, new) / min(old, new) > 10
