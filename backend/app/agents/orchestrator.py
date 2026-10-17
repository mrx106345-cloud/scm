"""Pipeline orchestrator (Part F2, P1-10)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.agents.base import Agent, AgentResult, RunContext

ORDER = ["data", "demand", "supplier", "logistics", "inventory", "alert", "explainer", "action"]
# Dependents skipped when one of these fails.
DEPENDS: dict[str, list[str]] = {
    "data": ["demand", "supplier", "logistics", "inventory", "alert", "explainer", "action"],
    "demand": ["inventory", "alert", "explainer", "action"],
    "supplier": ["inventory", "alert", "explainer", "action"],
    "inventory": ["alert", "explainer", "action"],
}


@dataclass
class RunRecord:
    """One pipeline run's outcome."""

    run_id: str
    status: str = "ok"  # ok | partial | failed
    agent_status: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class Orchestrator:
    """Runs registered agents in ORDER with retries and a run lock."""

    def __init__(self, max_retries: int = 2) -> None:
        """Init with retry budget."""
        self.max_retries = max_retries
        self._locked = False
        self._agents: dict[str, object] = {}

    def register(self, name: str, agent: object) -> None:
        """Register an agent implementation."""
        self._agents[name] = agent

    def run(self, ctx: RunContext) -> RunRecord:
        """Execute the full pipeline. Raises RuntimeError when busy."""
        if self._locked:
            raise RuntimeError("pipeline busy")
        self._locked = True
        try:
            rec = RunRecord(run_id=ctx.run_id)
            failed: set[str] = set()
            for name in ORDER:
                blocked = [f for f in failed if name in DEPENDS.get(f, [])]
                if blocked:
                    rec.agent_status[name] = "skipped"
                    rec.warnings.append(f"{name} skipped; upstream {blocked[0]} failed")
                    continue
                agent = self._agents.get(name)
                if agent is None:
                    rec.agent_status[name] = "skipped"
                    rec.warnings.append(f"{name} has no implementation yet")
                    continue
                result = self._run_with_retry(agent, ctx)  # type: ignore[arg-type]
                rec.agent_status[name] = result.status
                rec.warnings.extend(result.warnings)
                if result.status == "failed":
                    failed.add(name)
            rec.status = (
                "partial"
                if failed or any(v == "skipped" for v in rec.agent_status.values())
                else "ok"
            )
            if failed == set(ORDER):
                rec.status = "failed"
            return rec
        finally:
            self._locked = False

    def _run_with_retry(self, agent: Agent, ctx: RunContext) -> AgentResult:
        """Run one agent with backoff retries."""
        last: AgentResult = AgentResult(status="failed", warnings=["no attempt"])
        for attempt in range(self.max_retries + 1):
            try:
                run_fn = agent.run
                last = run_fn(ctx)
                if last.status != "failed":
                    return last
            except Exception as exc:  # noqa: BLE001
                last = AgentResult(status="failed", warnings=[f"{type(exc).__name__}: {exc}"])
            time.sleep(0.01 * (2**attempt))
        return last
