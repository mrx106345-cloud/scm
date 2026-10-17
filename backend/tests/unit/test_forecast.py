"""P1-07 tests: WAPE, backtest selection, 3% naive rule."""

from __future__ import annotations

from app.forecasting.methods import select_method, wape


def test_wape_basic() -> None:
    assert wape([10, 10], [8, 12]) == 0.2
    assert wape([], []) == 0.0


def test_backtest_prefers_stable_on_flat() -> None:
    series = [20.0] * 60
    sel = select_method(series, "smooth")
    assert sel["method"] == "naive"
    assert sel["wape"] == 0.0


def test_croston_on_intermittent() -> None:
    series = ([0.0] * 3 + [30.0]) * 15
    sel = select_method(series, "intermittent")
    assert sel["method"] in ("croston_sba", "moving_average_13", "naive")


def test_three_percent_rule() -> None:
    series = [10.0, 11.0, 10.0, 11.0] * 15
    sel = select_method(series, "smooth")
    assert sel["wape"] <= sel["wape_naive"]
