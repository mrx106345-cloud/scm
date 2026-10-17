"""Agent base interface (Part F1). Plain Python classes; no frameworks.

Every run is audited with duration and counts. Agents are idempotent per run_id.
LLM output may never trigger an action (security-guardrails).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class RunContext:
    """Inputs every agent receives."""

    run_id: str
    as_of_date: str  # ISO date YYYY-MM-DD
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Outputs every agent returns."""

    status: str  # ok | partial | failed
    items_processed: int = 0
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class Agent(Protocol):
    """Common agent interface."""

    name: str

    def run(self, ctx: RunContext) -> AgentResult:
        """Execute the agent for one pipeline run."""
        ...
