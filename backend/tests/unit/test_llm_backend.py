"""P2-01/P2-02 tests: LLM backends + explainer prompt + facts builders."""

from __future__ import annotations

from pathlib import Path

from app.llm.backends import LlamaCppBackend, MockBackend
from app.llm.facts import AlertExplanationFacts

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "app" / "llm" / "prompts" / "explain_alert.txt"
)


def _facts() -> AlertExplanationFacts:
    return AlertExplanationFacts(
        item_name="Hex Bolt M8",
        site="Plant-A",
        on_hand=120.0,
        days_to_stockout=9.0,
        supplier_name="Fasteners Ltd",
        lead_time_days=21.0,
        stockout_probability_pct=62.0,
        expected_loss="125000.00",
        suggested_qty=400.0,
        extra_cost="18000.00",
        severity="high",
        alert_type="stockout_risk",
    )


def test_mock_backend_is_deterministic() -> None:
    b = MockBackend()
    r1 = b.generate("hello", max_tokens=64)
    r2 = b.generate("hello", max_tokens=64)
    assert r1 == r2
    assert isinstance(r1, str) and len(r1) > 0


def test_mock_backend_schema_echo_contains_facts_marker() -> None:
    b = MockBackend()
    out = b.generate(
        "explain",
        max_tokens=64,
        json_schema={"properties": {"summary": {"type": "string"}}},
    )
    assert "summary" in out


def test_llamacpp_backend_errors_without_model_file(tmp_path: Path) -> None:
    b = LlamaCppBackend(model_path=str(tmp_path / "missing.gguf"))
    try:
        b.generate("hi", max_tokens=16)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "model file" in str(e)


def test_explainer_prompt_file_exists_with_placeholders() -> None:
    assert PROMPT_PATH.is_file()
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{facts_json}" in text
    assert "Do not calculate or invent any number" in text


def test_facts_serialize_to_json_with_computed_values_only() -> None:
    f = _facts()
    payload = f.to_json_dict()
    assert payload["item_name"] == "Hex Bolt M8"
    assert payload["days_to_stockout"] == 9.0
    assert payload["stockout_probability_pct"] == 62.0
    assert set(payload) == {
        "item_name",
        "site",
        "on_hand",
        "days_to_stockout",
        "supplier_name",
        "lead_time_days",
        "stockout_probability_pct",
        "expected_loss",
        "suggested_qty",
        "extra_cost",
        "severity",
        "alert_type",
    }
