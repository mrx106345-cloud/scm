"""LLM backend interface (Part H1). Protocol + Mock + llama.cpp backends.

The LLM only phrases explanations from computed facts; it never calculates.
All numbers shown to users are validated against the facts object first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMBackend(Protocol):
    """Common LLM interface (spec Part H1)."""

    def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.2,
        json_schema: dict[str, object] | None = None,
        stop: list[str] | None = None,
    ) -> str:
        """Generate text. Implementations must stay offline and CPU-only."""
        ...


@dataclass
class MockBackend:
    """Deterministic outputs for tests (tech-stack policy)."""

    canned_summary: str = "Stock is low and a delay is expected."

    def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.2,
        json_schema: dict[str, object] | None = None,
        stop: list[str] | None = None,
    ) -> str:
        _ = (prompt, max_tokens, temperature, stop)
        if json_schema is not None:
            props = json_schema.get("properties", {})
            keys = list(props.keys()) if isinstance(props, dict) else ["summary"]
            body = ", ".join(f'"{k}": "{self.canned_summary}"' for k in keys)
            return "{" + body + "}"
        return self.canned_summary


class LlamaCppBackend:
    """llama-cpp-python backend: GGUF model from config, CPU only.

    No model file is bundled; the owner supplies the path (tech-stack).
    The import is lazy so unit tests never require the native package.
    """

    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int = 4) -> None:
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads

    def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.2,
        json_schema: dict[str, object] | None = None,
        stop: list[str] | None = None,
    ) -> str:
        from pathlib import Path

        if not Path(self.model_path).is_file():
            raise RuntimeError(
                f"LLM model file not found: {self.model_path}. "
                "Set SCM_LLM_MODEL_PATH to a local GGUF file."
            )
        from llama_cpp import Llama  # type: ignore[import-not-found]

        llm = Llama(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_threads=self.n_threads,
            verbose=False,
        )
        kwargs: dict[str, object] = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stop or [],
        }
        if json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_object",
                "schema": json_schema,
            }
        out = llm.create_completion(**kwargs)  # type: ignore[arg-type]
        choices = out.get("choices", [])
        if not choices:
            raise RuntimeError("LLM returned no completion choices")
        return str(choices[0].get("text", ""))
