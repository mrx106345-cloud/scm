"""P1-04 test: generator is deterministic and canonical."""

from __future__ import annotations

import json
from pathlib import Path

from tools.synth_data.generate import generate  # noqa: E402


def test_generate_small(tmp_path: object) -> None:
    out = Path(str(tmp_path)) / "s1"
    s1 = generate(out, n_items=5, seed=7)
    gt1 = json.loads((out / "ground_truth.json").read_text())
    out2 = Path(str(tmp_path)) / "s2"
    s2 = generate(out2, n_items=5, seed=7)
    gt2 = json.loads((out2 / "ground_truth.json").read_text())
    assert s1 == s2
    assert gt1 == gt2
    assert (out / "consumption.csv").exists()
    assert (out / "items.csv").exists()
    assert len(gt1["injected_events"]["supplier_delays"]) == 15
    assert len(gt1["injected_events"]["data_defects"]) == 20
