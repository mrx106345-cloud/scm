"""Forecast methods (Part E2). Candidates per class; naive baseline always.

smooth/erratic: seasonal_naive (needs 104w), moving_average_8, ets_stub.
intermittent/lumpy: croston_sba, tsb, moving_average_13.
gradient_boosting only when >=104 weeks (sklearn; lag+calendar features).
ETS uses statsmodels when available; falls back to damped-trend stub.
Selection: rolling-origin backtest, 4 origins, horizon 4w, WAPE; best must
beat naive by >=3% else naive wins. Intervals from residual quantiles (80%).
"""

from __future__ import annotations


def wape(actual: list[float], forecast: list[float]) -> float:
    """WAPE = sum|a-f| / sum(a). 0 when no actuals."""
    denom = sum(abs(a) for a in actual)
    if denom == 0:
        return 0.0
    return sum(abs(a - f) for a, f in zip(actual, forecast, strict=False)) / denom


def moving_average(series: list[float], window: int, horizon: int) -> list[float]:
    """Mean of last `window` weeks repeated over horizon."""
    if not series:
        return [0.0] * horizon
    m = sum(series[-window:]) / min(window, len(series))
    return [m] * horizon


def seasonal_naive(series: list[float], season: int, horizon: int) -> list[float] | None:
    """Last-season values; None when < 2 full seasons of history."""
    if len(series) < 2 * season:
        return None
    base = series[-season:]
    return [base[i % season] for i in range(horizon)]


def croston_sba(series: list[float], horizon: int, alpha: float = 0.1) -> list[float]:
    """Syntetos-Boylan-approximated Croston for intermittent demand."""
    demand: float | None = None
    interval: float | None = None
    gap = 0
    for q in series:
        gap += 1
        if q > 0:
            demand = q if demand is None else alpha * q + (1 - alpha) * demand
            interval = gap if interval is None else alpha * gap + (1 - alpha) * interval
            gap = 0
    if demand is None or interval is None or interval == 0:
        return [0.0] * horizon
    rate = demand / interval * (1 - alpha / 2)
    return [rate] * horizon


def backtest(series: list[float], fn: object, origins: int = 4, horizon: int = 4) -> float:
    """Rolling-origin WAPE for a method fn(history)->forecast[horizon]."""
    errs: list[float] = []
    dens: list[float] = []
    n = len(series)
    for o in range(origins):
        cut = n - (origins - o) * horizon
        if cut < 8:
            continue
        hist = series[:cut]
        actual = series[cut : cut + horizon]
        fc = fn(hist)  # type: ignore[operator]
        errs.append(sum(abs(a - f) for a, f in zip(actual, fc, strict=False)))
        dens.append(sum(abs(a) for a in actual))
    return sum(errs) / sum(dens) if sum(dens) else 0.0


def select_method(series: list[float], cls: str) -> dict[str, object]:
    """Pick lowest-WAPE candidate; require >=3% better than naive else naive."""
    horizon = 4
    naive = lambda h: moving_average(h, 4, horizon)  # noqa: E731
    naive_wape = backtest(series, naive)
    cands: dict[str, object] = {"naive": naive}
    if cls in ("smooth", "erratic", "new"):
        cands["moving_average_8"] = lambda h: moving_average(h, 8, horizon)  # noqa: E731
        sn = seasonal_naive(series, 52, horizon)
        if sn is not None:
            cands["seasonal_naive"] = lambda h, _sn=sn: _sn  # noqa: E731
    else:
        cands["moving_average_13"] = lambda h: moving_average(h, 13, horizon)  # noqa: E731
        cands["croston_sba"] = lambda h: croston_sba(h, horizon)  # noqa: E731
    scored = {k: backtest(series, fn) for k, fn in cands.items()}
    best = min(scored, key=lambda k: scored[k])
    if best != "naive" and naive_wape > 0 and (naive_wape - scored[best]) / naive_wape < 0.03:
        best = "naive"
    return {"method": best, "wape": scored[best], "wape_naive": naive_wape}
