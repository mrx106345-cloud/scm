"""LLM benchmark (Part H1): 50 fixed explanation prompts on the real backend.

Reports peak RAM (must stay <= 4 GB on the 4-core target), median
tokens/second, validator pass rate and template-fallback rate. Skips with a
clear message when no GGUF model file is configured (owner has not chosen one).
Offline: loads only a local file; makes no network calls.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.llm.backends import LlamaCppBackend, MockBackend
from app.llm.explainer import build_prompt
from app.llm.facts import AlertExplanationFacts
from app.llm.validator import validate_numbers

N_PROMPTS = 50
RAM_LIMIT_GB = 4.0


def build_case_facts(i: int) -> AlertExplanationFacts:
    """Deterministic synthetic alert facts for case i (no real data)."""
    severities = ["critical", "high", "medium"]
    types = ["stockout_risk", "supplier_delay", "excess"]
    return AlertExplanationFacts(
        item_name=f"Item-{1000 + i}",
        site=f"Plant-{(i % 3) + 1}",
        on_hand=float(50 + (i * 37) % 900),
        days_to_stockout=float(1 + (i * 13) % 30),
        supplier_name=f"Supplier-{(i % 7) + 1}",
        lead_time_days=float(7 + (i * 11) % 38),
        stockout_probability_pct=float((i * 17) % 100),
        expected_loss=f"{1000 * (1 + (i * 29) % 500)}.00",
        suggested_qty=float(100 + (i * 41) % 900),
        extra_cost=f"{100 * (1 + (i * 23) % 200)}.00",
        severity=severities[i % 3],
        alert_type=types[i % 3],
    )


def peak_rss_gb() -> float | None:
    """Peak resident set size in GB (ru_maxrss); None when unavailable."""
    try:
        import resource

        peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB; macOS reports bytes — normalize by magnitude.
        if peak_kb > 1 << 32:
            return peak_kb / (1 << 30)
        return peak_kb / (1 << 20)
    except (ImportError, OSError, ValueError):
        return None


def run(n: int = N_PROMPTS, model_path: str | None = None) -> dict[str, object]:
    """Run the benchmark; returns the metrics dict (also printed as JSON)."""
    path = model_path or os.environ.get("SCM_LLM_MODEL_PATH", "")
    if not path or not Path(path).is_file():
        return {
            "status": "skipped",
            "reason": "no GGUF model file configured (SCM_LLM_MODEL_PATH). "
            "Owner must choose a model and verify its license first.",
            "n_prompts": n,
        }
    backend: LlamaCppBackend | MockBackend = LlamaCppBackend(model_path=path)
    latencies: list[float] = []
    tokens: list[int] = []
    validated = 0
    fallbacks = 0
    facts_seen: list[AlertExplanationFacts] = []
    for i in range(n):
        facts = build_case_facts(i)
        facts_seen.append(facts)
        prompt = build_prompt(facts)
        start = time.perf_counter()
        try:
            raw = backend.generate(prompt, max_tokens=256, temperature=0.2)
        except RuntimeError as e:
            return {"status": "error", "reason": str(e), "n_prompts": n}
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)
        tokens.append(max(1, len(raw.split())))
        ok, _ = validate_numbers(raw, facts.to_json_dict())
        if ok:
            validated += 1
        else:
            second = backend.generate(prompt, max_tokens=256, temperature=0.0)
            ok2, _ = validate_numbers(second, facts.to_json_dict())
            if ok2:
                validated += 1
            else:
                fallbacks += 1
    total_s = sum(latencies)
    result: dict[str, object] = {
        "status": "ok",
        "n_prompts": n,
        "model_path": path,
        "median_latency_s": round(statistics.median(latencies), 3),
        "median_tokens_per_s": round(
            statistics.median(t / s for t, s in zip(tokens, latencies)), 1
        ),
        "total_s": round(total_s, 1),
        "validator_pass_rate": round(validated / n, 4),
        "template_fallback_rate": round(fallbacks / n, 4),
        "peak_rss_gb": round(v, 3) if (v := peak_rss_gb()) is not None else None,
        "ram_limit_gb": RAM_LIMIT_GB,
    }
    peak = result["peak_rss_gb"]
    result["ram_within_limit"] = peak is None or float(peak) <= RAM_LIMIT_GB
    result["_facts_seen"] = len(facts_seen)
    return result


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_PROMPTS
    model = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(run(n, model), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
