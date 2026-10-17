"""Dashboard summary models (api-spec A3). Money Decimal strings, UTC ISO times."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AlertCounts(BaseModel):
    """Counts by severity."""

    model_config = ConfigDict(extra="forbid")

    critical: int = 0
    high: int = 0
    medium: int = 0


class MoneyAmount(BaseModel):
    """Money as Decimal string + estimate label."""

    model_config = ConfigDict(extra="forbid")

    amount: str = Field(pattern=r"^-?\d+\.\d{2}$")
    label: str = "estimate"


class DashboardSummary(BaseModel):
    """GET /api/v1/dashboard/summary response (viewer+)."""

    model_config = ConfigDict(extra="forbid")

    as_of: str
    alerts: AlertCounts
    expected_loss_at_risk: MoneyAmount
    data_quality: dict[str, int]
    pending_recommendations: int = 0
