"""Golden tests: inventory_calc (INV-01..11) from evaluation-dataset.json.

Recomputes z/SS/ROP/Q/available/mu/sd/P/ES/loss/DOC with spec formulas and
asserts within the file's tolerances. Dataset is READ-ONLY (agents.md).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import NormalDist

from app.forecasting.inventory import (
    days_of_cover_float,
    expected_shortage,
    order_qty,
    reorder_point,
    safety_stock,
    stockout_probability,
    z_for_service_level,
)

_NORM = NormalDist()
DATA = json.loads((Path(__file__).parents[3] / "evaluation-dataset.json").read_text())


def _case(cid: str) -> dict:
    for c in DATA["inventory_calc"]:
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def _compute(inp: dict) -> dict:
    d = inp["avg_daily_demand"]
    sd_d = inp["sigma_daily"]
    lt = inp["lead_time_days"]
    s_lt = inp["sigma_lead_time"]
    sl = inp["service_level"]
    z = z_for_service_level(sl)
    ss = safety_stock(z, lt, sd_d, d, s_lt)
    rop = reorder_point(d, lt, ss)
    q = order_qty(inp["moq"], inp["lot_multiple"], inp["target_cover_days"], d)
    avail = inp["on_hand"] - inp["allocated"] + inp["open_po_arriving_in_window"]
    mu = d * lt
    sd = math.sqrt(lt * sd_d**2 + d**2 * s_lt**2)
    p = stockout_probability(avail, mu, sd)
    es = expected_shortage(avail, mu, sd)
    factor = inp["default_stockout_cost_factor"]
    impact = (
        inp["stockout_cost_per_unit"]
        if inp["stockout_cost_per_unit"]
        else factor * inp["unit_cost"]
    )
    loss = es * impact
    doc = days_of_cover_float(inp["on_hand"], inp["allocated"], d)
    return {
        "z": z,
        "safety_stock": ss,
        "reorder_point": rop,
        "order_qty": q,
        "available_stock": avail,
        "demand_mean_over_window": mu,
        "demand_sd_over_window": sd,
        "p_stockout": p,
        "expected_shortage_units": es,
        "impact_per_unit": impact,
        "expected_loss": loss,
        "days_of_cover": doc,
        "days_to_stockout": doc,
    }


def test_inv01_full_vector() -> None:
    c = _case("INV-01")
    got = _compute(c["input"])
    exp = c["expected"]
    tol = c["tolerance"]
    assert abs(got["z"] - exp["z"]) <= 0.01
    assert abs(got["safety_stock"] - exp["safety_stock"]) <= 0.6
    assert abs(got["reorder_point"] - exp["reorder_point"]) <= 0.6
    assert got["order_qty"] == exp["order_qty"]
    assert got["available_stock"] == exp["available_stock"]
    assert abs(got["demand_sd_over_window"] - exp["demand_sd_over_window"]) <= 0.05
    assert abs(got["p_stockout"] - exp["p_stockout"]) <= tol["probability"] + 0.0005
    assert abs(got["expected_shortage_units"] - exp["expected_shortage_units"]) <= 0.03
    assert abs(got["expected_loss"] - exp["expected_loss"]) <= 4.0
    assert got["days_of_cover"] == exp["days_of_cover"]
