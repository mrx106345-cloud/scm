"""Explainer (Parts H2/H3). Build prompt, generate, validate, retry, fallback.

Retry once at temperature 0, then use the deterministic template and mark
source "template". Records source, retries and validator result in the
explanation JSON; template-fallback rate is tracked in metrics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from app.llm.backends import LLMBackend
from app.llm.facts import AlertExplanationFacts
from app.llm.validator import validate_numbers

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "explain_alert.txt"


def build_prompt(facts: AlertExplanationFacts) -> str:
    """Render the explainer prompt with the facts JSON (spec Part H2)."""
    import json

    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{facts_json}", json.dumps(facts.to_json_dict()))


class _GenerateFn(Protocol):
    def __call__(self, prompt: str, temperature: float) -> str: ...


def _template_fallback(facts: AlertExplanationFacts) -> dict[str, str]:
    """Deterministic f-string text per alert type (spec Part H3 step 3)."""
    d = facts.to_json_dict()
    sev = str(d.get("severity", ""))
    item = str(d.get("item_name", ""))
    site = str(d.get("site", ""))
    days = d.get("days_to_stockout")
    supplier = str(d.get("supplier_name", ""))
    lead = d.get("lead_time_days")
    prob = d.get("stockout_probability_pct")
    qty = d.get("suggested_qty")
    loss = str(d.get("expected_loss", ""))
    cost = str(d.get("extra_cost", ""))
    atype = str(d.get("alert_type", ""))
    if atype == "supplier_delay":
        return {
            "summary": f"{supplier} is slower than planned for {item}.",
            "why": (
                f"Orders take {lead} days to arrive at {site} and the delay "
                f"puts cover at {days} days, with a {prob} percent chance of a gap."
            ),
            "suggested_action": (
                f"Order {qty} units now; extra cost is {cost} against {loss} at risk."
            ),
        }
    if atype in ("excess", "dead_stock"):
        return {
            "summary": f"{item} at {site} holds excess cover.",
            "why": (
                f"On hand covers {days} days against a {days}-day need, so cash is "
                f"tied up rated {sev}."
            ),
            "suggested_action": f"Move or pause {qty} units before reordering.",
        }
    if atype == "data_quality":
        return {
            "summary": f"{item} at {site} needs a data fix before planning.",
            "why": (
                f"Lead time is {lead} days from {supplier}; until the defect is "
                f"fixed the {prob} percent risk figure cannot be trusted."
            ),
            "suggested_action": "Fix the listed defect, then re-run the pipeline.",
        }
    # stockout_risk (default): every number comes straight from facts.
    return {
        "summary": f"{item} at {site} may run out in {days} days.",
        "why": (
            f"{supplier} takes {lead} days to deliver and there is a {prob} "
            f"percent chance of a gap, rated {sev} with {loss} at risk."
        ),
        "suggested_action": f"Order {qty} units now; extra cost is {cost}.",
    }


def explain_alert(
    facts: AlertExplanationFacts, backend: LLMBackend, metrics: dict[str, Any] | None = None
) -> dict[str, object]:
    """Generate an explanation; retry once at temp 0; else template.

    Returns {"summary", "why", "suggested_action", "source", "retries",
    "validator"}; source is "llm" or "template". LLM output never triggers
    any action — this function only returns text.
    """
    import json

    prompt = build_prompt(facts)
    payload = facts.to_json_dict()

    def attempt(temperature: float) -> tuple[dict[str, str], bool]:
        raw = backend.generate(
            prompt,
            max_tokens=512,
            temperature=temperature,
            json_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "why": {"type": "string"},
                    "suggested_action": {"type": "string"},
                },
            },
        )
        try:
            parsed = json.loads(raw)
            cand = {
                "summary": str(parsed.get("summary", "")),
                "why": str(parsed.get("why", "")),
                "suggested_action": str(parsed.get("suggested_action", "")),
            }
        except (ValueError, AttributeError):
            return {"summary": "", "why": "", "suggested_action": ""}, False
        text = f"{cand['summary']} {cand['why']} {cand['suggested_action']}"
        ok, _ = validate_numbers(text, payload)
        return cand, ok

    first, ok_first = attempt(0.2)
    retries = 0
    if ok_first:
        result = {**first, "source": "llm", "retries": retries, "validator": "pass"}
    else:
        retries = 1
        second, ok_second = attempt(0.0)
        if ok_second:
            result = {**second, "source": "llm", "retries": retries, "validator": "pass"}
        else:
            result = {
                **_template_fallback(facts),
                "source": "template",
                "retries": retries,
                "validator": "fail",
            }
    if metrics is not None:
        metrics["template_fallback_rate"] = metrics.get("template_fallback_rate", 0) + (
            1 if result["source"] == "template" else 0
        )
    return result
