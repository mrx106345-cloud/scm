"""Golden tests: alert_severity + alert_score + supplier_risk + quality score."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from app.agents.alerting import alert_score, alert_severity, supplier_risk, supplier_trend_flag
from app.pipeline.quality import quality_score

DATA = json.loads((Path(__file__).parents[3] / "evaluation-dataset.json").read_text())


def test_alert_severity_all() -> None:
    for c in DATA["alert_severity"]:
        got = alert_severity(
            c["input"]["p_stockout"],
            c["input"].get("days_to_stockout"),
            c["input"].get("criticality", "C"),
        )
        assert (got or "none") == c["expected"]["severity"], c["id"]


def test_alert_score_all() -> None:
    for c in DATA["alert_score"]:
        got = alert_score(c["input"]["expected_loss"], c["input"]["days_to_stockout"])
        assert abs(got - c["expected"]["score"]) <= 0.6, c["id"]


def _derive_supplier(inp: dict) -> tuple[float, float, float]:
    leads: list[float] = inp["last_15_lead_times_days"]
    recent = leads[-5:]
    prior = leads[-15:-5]
    mean_recent = mean(recent)
    mean_prior = mean(prior)
    drift = (mean_recent - mean_prior) / mean_prior if mean_prior else 0.0
    delays: list[float] = inp["last_10_delay_days_vs_promised"]
    grace = 1
    otr = sum(1 for x in delays if x <= grace) / len(delays)
    return drift, otr, inp["dependency_share"]


def test_supplier_risk_all() -> None:
    for c in DATA["supplier_risk"]:
        drift, otr, dep = _derive_supplier(c["input"])
        exp = c["expected"]
        assert abs(drift - exp["drift_pct"]) <= 0.002, c["id"]
        assert abs(otr - exp["on_time_rate"]) <= 0.01, c["id"]
        got = supplier_risk(drift, otr, dep)
        assert got == exp["risk_score"], c["id"]
        flag = supplier_trend_flag(c["input"]["last_15_lead_times_days"], drift)
        assert flag == exp["trend_flag"], c["id"]


def test_quality_score_all() -> None:
    for c in DATA["data_quality_score"]:
        got = quality_score(
            c["input"]["critical_check_types_failed"], c["input"]["warning_check_types_failed"]
        )
        assert got == c["expected"]["score"], c["id"]
