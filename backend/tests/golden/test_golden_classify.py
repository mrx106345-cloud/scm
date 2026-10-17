"""Golden: demand_classification (5 cases)."""

from __future__ import annotations

import json
from pathlib import Path

from app.forecasting.classify import classify_series

DATA = json.loads((Path(__file__).parents[3] / "evaluation-dataset.json").read_text())


def test_classification_all() -> None:
    for c in DATA["demand_classification"]:
        got = classify_series(list(c["input"]["weekly_demand"]))
        assert got["class"] == c["expected"]["class"], c["id"]
