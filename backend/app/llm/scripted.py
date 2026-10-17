"""Deterministic scripted backend for validator/explainer tests.

Returns canned outputs in order; repeats the last one when exhausted.
"""

from __future__ import annotations


class ScriptedBackend:
    """Scripted outputs for tests (spec allows a deterministic test backend)."""

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0

    def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.2,
        json_schema: dict[str, object] | None = None,
        stop: list[str] | None = None,
    ) -> str:
        _ = (prompt, max_tokens, temperature, json_schema, stop)
        out = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return out
