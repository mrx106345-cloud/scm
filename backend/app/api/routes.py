"""Thin API routes. No business logic here — services/agents own it (P1-11)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.dashboard import AlertCounts, DashboardSummary, MoneyAmount
from app.core.dependencies import require_role
from app.db.models import Alert, Recommendation
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/v1")


@router.get("/dashboard/summary")
def dashboard_summary(
    _user: dict[str, object] = Depends(require_role("viewer")),  # noqa: B008
) -> DashboardSummary:
    """Return dashboard counts (alerts/loss/pending from DB; DQ needs persistence)."""
    session = SessionLocal()
    try:
        counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0}
        rows = session.execute(
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.status.in_(("open", "acknowledged")))
            .group_by(Alert.severity)
        ).all()
        for severity, count in rows:
            if severity in counts:
                counts[severity] = int(count)
        expected_loss = session.scalar(
            select(func.coalesce(func.sum(Alert.expected_loss), 0.0)).where(
                Alert.status.in_(("open", "acknowledged"))
            )
        )
        pending = session.scalar(
            select(func.count(Recommendation.id)).where(Recommendation.status == "pending")
        )
        # Data quality is not persisted yet (needs owner-approved schema state);
        # report the last-known placeholder range transparently until then.
        return DashboardSummary(
            as_of=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            alerts=AlertCounts(
                critical=counts["critical"], high=counts["high"], medium=counts["medium"]
            ),
            expected_loss_at_risk=MoneyAmount(amount=f"{float(expected_loss or 0.0):.2f}"),
            data_quality={"score": 0, "critical_issues": 0, "warnings": 0},
            pending_recommendations=int(pending or 0),
        )
    finally:
        session.close()
