"""Pipeline perf bench: 200 item-series < 2 min; 5000 < 10 min on 4 cores.

Measures classify + select_method + inventory math + alert severity/score
per series (the CPU-hot path). Run: python tools/bench_pipeline.py [n].
"""

from __future__ import annotations

import random
import sys
import time

sys.path.insert(0, "backend")
from app.agents.alerting import alert_score, alert_severity
from app.forecasting.classify import classify_series
from app.forecasting.inventory import (
    order_qty,
    reorder_point,
    safety_stock,
    stockout_probability,
    z_for_service_level,
)
from app.forecasting.methods import select_method


def one_series(weekly: list[float], idx: int) -> None:
    """Run the hot path once for a single item-site series."""
    cls = classify_series(weekly)["class"]
    assert isinstance(cls, str)
    select_method(weekly, cls)
    z = z_for_service_level(0.95)
    ss = safety_stock(z, 14.0, 6.0, 20.0, 2.0)
    reorder_point(20.0, 14.0, ss)
    order_qty(100, 50, 30, 20.0)
    p = stockout_probability(400.0, 280.0, 45.87)
    sev = alert_severity(p, 20.0, "B")
    assert sev is None or isinstance(sev, str)
    alert_score(31.89, 20.0)


def bench(n: int, seed: int = 7) -> float:
    """Bench n series; return elapsed seconds."""
    rng = random.Random(seed)
    series = [[max(0.0, rng.gauss(140, 40)) for _ in range(156)] for _ in range(n)]
    start = time.perf_counter()
    for i, w in enumerate(series):
        one_series(w, i)
    return time.perf_counter() - start


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    el = bench(n)
    per = el / n * 1000
    print(f"series={n} elapsed={el:.2f}s per_series={per:.2f}ms")
    budget = 120.0 if n <= 200 else 600.0
    print("PASS" if el < budget else "FAIL", f"(budget {budget:.0f}s)")
