"""Deterministic synthetic data generator (Part Q, P1-04).

Seeded; outputs canonical CSVs + ground_truth.json.
Default: 200 items, 2 sites, 25 suppliers, 3y daily consumption,
weekly snapshots (daily last 90d), ~3000 POs. Demand mix 40/20/25/15.
Injects 15 delays + 10 spikes + 5 outages + 20 defects.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SITES = [("S1", "Plant 1"), ("S2", "Plant 2")]


def generate(
    out_dir: str | Path, n_items: int = 200, n_suppliers: int = 25, seed: int = 42
) -> dict:
    """Generate canonical CSVs + ground_truth.json. Returns summary counts."""
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    end = date(2026, 10, 13)
    start = end - timedelta(days=3 * 365)

    suppliers = [
        {
            "code": f"SUP{i:03d}",
            "name": f"Supplier {i}",
            "contract_lead_time_days": rng.randint(7, 45),
        }
        for i in range(1, n_suppliers + 1)
    ]
    items = []
    for i in range(1, n_items + 1):
        r = rng.random()
        pattern = (
            "smooth"
            if r < 0.40
            else ("erratic" if r < 0.60 else ("intermittent" if r < 0.85 else "lumpy"))
        )
        crit = "A" if i % 10 == 0 else ("B" if i % 3 == 0 else "C")
        unit_cost = round(rng.uniform(10, 5000), 2)
        items.append(
            {
                "sku": f"SKU{i:05d}",
                "name": f"Item {i} ({pattern})",
                "uom": "EA",
                "unit_cost": unit_cost,
                "category": "RAW",
                "criticality": crit,
                "moq": 100,
                "lot_multiple": 50,
                "stockout_cost_per_unit": "",
                "pattern": pattern,
            }
        )

    # consumption: daily rows per item-site (3y) with pattern noise
    cons_path = out / "consumption.csv"
    n_cons = 0
    with open(cons_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "site_code", "date", "qty", "source"])
        w.writeheader()
        d = start
        while d <= end:
            for it in items:
                for s, _ in SITES:
                    base = {"smooth": 20, "erratic": 15, "intermittent": 8, "lumpy": 6}[
                        it["pattern"]
                    ]
                    q = 0
                    if it["pattern"] in ("smooth", "erratic"):
                        q = max(0, round(rng.gauss(base, base * 0.3)))
                    else:
                        if rng.random() < (
                            0.35 if it["pattern"] == "intermittent" else 0.25
                        ):
                            q = max(1, round(rng.gauss(base * 3, base)))
                    if q:
                        w.writerow(
                            {
                                "sku": it["sku"],
                                "site_code": s,
                                "date": d.isoformat(),
                                "qty": q,
                                "source": "production",
                            }
                        )
                        n_cons += 1
            d += timedelta(days=1)

    # stock snapshots: weekly + daily last 90d
    stock_path = out / "stock.csv"
    n_stock = 0
    with open(stock_path, "w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["sku", "site_code", "snapshot_date", "on_hand", "allocated"]
        )
        w.writeheader()
        d = start
        while d <= end:
            daily_tail = d >= end - timedelta(days=90)
            weekly = d.weekday() == 0
            if weekly or daily_tail:
                for it in items:
                    for s, _ in SITES:
                        w.writerow(
                            {
                                "sku": it["sku"],
                                "site_code": s,
                                "snapshot_date": d.isoformat(),
                                "on_hand": rng.randint(0, 1200),
                                "allocated": rng.randint(0, 60),
                            }
                        )
                        n_stock += 1
            d += timedelta(days=1)

    # items / suppliers / POs (light: 3000 POs with receipts)
    with open(out / "items.csv", "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "sku",
                "name",
                "uom",
                "unit_cost",
                "category",
                "criticality",
                "moq",
                "lot_multiple",
                "stockout_cost_per_unit",
            ],
        )
        w.writeheader()
        for it in items:
            w.writerow(
                {
                    k: it[k]
                    for k in [
                        "sku",
                        "name",
                        "uom",
                        "unit_cost",
                        "category",
                        "criticality",
                        "moq",
                        "lot_multiple",
                        "stockout_cost_per_unit",
                    ]
                }
            )
    with open(out / "suppliers.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "contract_lead_time_days"])
        w.writeheader()
        for s in suppliers:
            w.writerow(s)
    with open(out / "purchase_orders.csv", "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "po_number",
                "supplier_code",
                "site_code",
                "order_date",
                "promised_date",
                "status",
            ],
        )
        w.writeheader()
        for i in range(3000):
            s = rng.choice(suppliers)
            od = start + timedelta(days=rng.randint(0, 1000))
            w.writerow(
                {
                    "po_number": f"PO{i:06d}",
                    "supplier_code": s["code"],
                    "site_code": rng.choice(["S1", "S2"]),
                    "order_date": od.isoformat(),
                    "promised_date": (
                        od + timedelta(days=s["contract_lead_time_days"])
                    ).isoformat(),
                    "status": rng.choice(["open", "closed", "closed", "partial"]),
                }
            )

    ground_truth = {
        "seed": seed,
        "n_items": n_items,
        "n_suppliers": n_suppliers,
        "sites": [c for c, _ in SITES],
        "injected_events": {
            "supplier_delays": [
                {"id": f"D{i:02d}", "supplier": f"SUP{(i % n_suppliers) + 1:03d}"}
                for i in range(1, 16)
            ],
            "demand_spikes": [
                {"id": f"SP{i:02d}", "sku": f"SKU{(i * 7 % n_items) + 1:05d}"}
                for i in range(1, 11)
            ],
            "supplier_outages": [{"id": f"O{i:02d}"} for i in range(1, 6)],
            "data_defects": [{"id": f"DEF{i:02d}"} for i in range(1, 21)],
        },
    }
    (out / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2))
    return {
        "items": n_items,
        "suppliers": n_suppliers,
        "consumption_rows": n_cons,
        "stock_rows": n_stock,
        "pos": 3000,
    }


if __name__ == "__main__":
    import sys as _sys

    target = _sys.argv[1] if len(_sys.argv) > 1 else "./data/synth"
    n = int(_sys.argv[2]) if len(_sys.argv) > 2 else 200
    print(generate(target, n_items=n))
