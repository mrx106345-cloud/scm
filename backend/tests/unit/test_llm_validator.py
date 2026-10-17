"""P2-03 tests: number validator (golden VAL-01..16) + retry/template fallback."""

from __future__ import annotations

import json
from pathlib import Path

from app.llm.explainer import build_prompt, explain_alert
from app.llm.facts import AlertExplanationFacts
from app.llm.scripted import ScriptedBackend
from app.llm.validator import validate_numbers

DATA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "evaluation-dataset.json"


def _golden_val_cases() -> list[dict[str, object]]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return list(data["number_validator"])


def test_golden_number_validator_all_16() -> None:
    cases = _golden_val_cases()
    assert len(cases) == 16
    for case in cases:
        facts = dict(case["facts"])  # type: ignore[arg-type]
        ok, unmatched = validate_numbers(str(case["llm_output"]), facts)
        expected = case["expected"] == "pass"
        assert ok == expected, f"{case['id']}: unmatched={unmatched}"


def test_prompt_contains_facts_json_and_schema_fields() -> None:
    facts = AlertExplanationFacts(
        item_name="Hex Bolt M8",
        site="Plant 1",
        on_hand=100.0,
        days_to_stockout=4.0,
        supplier_name="Alpha Steels",
        lead_time_days=18.0,
        stockout_probability_pct=62.0,
        expected_loss="240000.00",
        suggested_qty=500.0,
        extra_cost="12000.00",
        severity="high",
        alert_type="stockout_risk",
    )
    prompt = build_prompt(facts)
    assert "Hex Bolt M8" in prompt
    assert "Do not calculate or invent any number" in prompt


def test_explainer_passes_through_valid_llm_text() -> None:
    facts = AlertExplanationFacts(
        item_name="Hex Bolt M8",
        site="Plant 1",
        on_hand=100.0,
        days_to_stockout=4.0,
        supplier_name="Alpha Steels",
        lead_time_days=18.0,
        stockout_probability_pct=62.0,
        expected_loss="240000.00",
        suggested_qty=500.0,
        extra_cost="12000.00",
        severity="high",
        alert_type="stockout_risk",
    )
    good = (
        '{"summary": "Risk in 4 days.", "why": "Lead time is 18 days.", '
        '"suggested_action": "Order 500 units."}'
    )
    res = explain_alert(facts, ScriptedBackend([good]))
    assert res["source"] == "llm"
    assert res["retries"] == 0
    assert res["validator"] == "pass"


def test_explainer_retries_once_then_uses_template() -> None:
    facts = AlertExplanationFacts(
        item_name="Hex Bolt M8",
        site="Plant 1",
        on_hand=100.0,
        days_to_stockout=4.0,
        supplier_name="Alpha Steels",
        lead_time_days=18.0,
        stockout_probability_pct=62.0,
        expected_loss="240000.00",
        suggested_qty=500.0,
        extra_cost="12000.00",
        severity="high",
        alert_type="stockout_risk",
    )
    bad = '{"summary": "Risk in 5 days.", "why": "x", "suggested_action": "y"}'
    res = explain_alert(facts, ScriptedBackend([bad, bad]))
    assert res["source"] == "template"
    assert res["retries"] == 1
    assert res["validator"] == "fail"
    text = res["summary"] + " " + res["why"] + " " + res["suggested_action"]
    ok, unmatched = validate_numbers(text, facts.to_json_dict())
    assert ok, unmatched


def test_template_fallback_self_validates_for_all_types() -> None:
    for alert_type in (
        "stockout_risk",
        "supplier_delay",
        "excess",
        "dead_stock",
        "data_quality",
        "mystery",
    ):
        facts = AlertExplanationFacts(
            item_name="Hex Bolt M8",
            site="Plant 1",
            on_hand=100.0,
            days_to_stockout=4.0,
            supplier_name="Alpha Steels",
            lead_time_days=18.0,
            stockout_probability_pct=62.0,
            expected_loss="240000.00",
            suggested_qty=500.0,
            extra_cost="12000.00",
            severity="high",
            alert_type=alert_type,
        )
        res = explain_alert(facts, ScriptedBackend(['{"summary": "in 99 days"}']))
        assert res["source"] == "template"
        text = res["summary"] + " " + res["why"] + " " + res["suggested_action"]
        ok, unmatched = validate_numbers(text, facts.to_json_dict())
        assert ok, (alert_type, unmatched)
