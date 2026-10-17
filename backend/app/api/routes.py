"""Thin API routes. No business logic here — services/agents own it (P1-11)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dashboard import AlertCounts, DashboardSummary, MoneyAmount

router = APIRouter(prefix="/api/v1")


@router.get("/dashboard/summary")
def dashboard_summary() -> DashboardSummary:
    """Return dashboard counts (stub backed by services in P1-11 full)."""
    return DashboardSummary(
        as_of="2026-10-13T06:00:00Z",
        alerts=AlertCounts(critical=0, high=0, medium=0),
        expected_loss_at_risk=MoneyAmount(amount="0.00", label="estimate"),
        data_quality={"score": 100, "critical_issues": 0, "warnings": 0},
        pending_recommendations=0,
    )
