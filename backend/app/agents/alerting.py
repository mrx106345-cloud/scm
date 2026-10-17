"""Alert severity + score + supplier risk (Parts F3).

Severity: critical if P>=0.50 or days_to_stockout<=3 for A items;
high if P>=0.25; medium if P>=0.10; else none (dead-stock -> low info).
urgency = 1 + max(0, 14-days)/14 in [1,2]. score = expected_loss * urgency.
Rounding is half-up (evaluation-dataset clarification).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def round_half_up(x: float) -> int:
    """Round half-up to int (spec clarification)."""
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def alert_severity(
    p: float | None, days_to_stockout: float | None, criticality: str = "C"
) -> str | None:
    """Return severity or None when no alert. Zero-demand (days None) -> None."""
    if p is None:
        return None
    if days_to_stockout is None:
        return None
    if p >= 0.50 or (criticality == "A" and days_to_stockout <= 3):
        return "critical"
    if p >= 0.25:
        return "high"
    if p >= 0.10:
        return "medium"
    return None


def urgency(days_to_stockout: float) -> float:
    """1 + max(0, 14-days)/14, range [1,2]."""
    return 1.0 + max(0.0, 14.0 - days_to_stockout) / 14.0


def alert_score(expected_loss: float, days_to_stockout: float) -> float:
    """score = expected_loss * urgency."""
    return expected_loss * urgency(days_to_stockout)


def supplier_risk(drift_pct: float, on_time_rate: float, dependency_share: float) -> int:
    """risk = round_half_up(100*(0.40*clip(drift/0.5) + 0.35*(1-otr) + 0.25*dep))."""
    clip = max(0.0, min(1.0, drift_pct / 0.5))
    raw = 100.0 * (0.40 * clip + 0.35 * (1.0 - on_time_rate) + 0.25 * dependency_share)
    return round_half_up(raw)


def supplier_trend_flag(last_leads: list[float], drift_pct: float) -> bool:
    """True when last 4 strictly increasing (3 rises) OR drift >= 0.25."""
    if drift_pct >= 0.25:
        return True
    if len(last_leads) >= 4:
        tail = last_leads[-4:]
        if tail[0] < tail[1] < tail[2] < tail[3]:
            return True
    return False
