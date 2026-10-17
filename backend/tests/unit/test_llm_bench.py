"""P2-04 tests: llm_bench metrics shape (no model file needed)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "tools"))

import llm_bench

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def test_bench_skips_without_model_file() -> None:
    res = llm_bench.run(n=3, model_path=None)
    assert res["status"] == "skipped"
    assert res["n_prompts"] == 3


def test_bench_skips_when_file_missing(tmp_path: Path) -> None:
    res = llm_bench.run(n=3, model_path=str(tmp_path / "nope.gguf"))
    assert res["status"] == "skipped"


def test_bench_metrics_shape_with_mock_backend(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    from app.llm.backends import MockBackend

    model = tmp_path / "dummy.gguf"
    model.write_text("", encoding="utf-8")
    monkeypatch.setattr(llm_bench, "LlamaCppBackend", lambda model_path: MockBackend())
    res = llm_bench.run(n=5, model_path=str(model))
    assert res["status"] == "ok"
    assert res["n_prompts"] == 5
    assert isinstance(res["median_latency_s"], float)
    assert isinstance(res["median_tokens_per_s"], float)
    assert 0.0 <= float(res["validator_pass_rate"]) <= 1.0
    assert 0.0 <= float(res["template_fallback_rate"]) <= 1.0
    assert res["ram_limit_gb"] == 4.0
    assert res["ram_within_limit"] in (True, False)


def test_bench_case_facts_are_deterministic() -> None:
    f1 = llm_bench.build_case_facts(7).to_json_dict()
    f2 = llm_bench.build_case_facts(7).to_json_dict()
    assert f1 == f2
    assert f1["item_name"] == "Item-1007"
