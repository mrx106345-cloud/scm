"""P1-10 tests: order, retries, skip-on-failure, single-run lock."""

from __future__ import annotations

import pytest

from app.agents.base import AgentResult, RunContext
from app.agents.orchestrator import Orchestrator


class Ok:
    name = "ok"

    def run(self, ctx: RunContext) -> AgentResult:
        return AgentResult(status="ok", items_processed=1)


class Flaky:
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    def run(self, ctx: RunContext) -> AgentResult:
        self.calls += 1
        if self.calls < 2:
            raise ValueError("boom")
        return AgentResult(status="ok", items_processed=1)


class Bad:
    name = "bad"

    def run(self, ctx: RunContext) -> AgentResult:
        return AgentResult(status="failed", warnings=["nope"])


def _ctx() -> RunContext:
    return RunContext(run_id="r1", as_of_date="2026-10-13")


def test_partial_when_no_agents() -> None:
    rec = Orchestrator().run(_ctx())
    assert rec.status == "partial"


def test_retry_recovers() -> None:
    o = Orchestrator()
    o.register("data", Flaky())
    rec = o.run(_ctx())
    assert rec.agent_status["data"] == "ok"


def test_failure_skips_dependents() -> None:
    o = Orchestrator()
    o.register("data", Bad())
    o.register("demand", Ok())
    rec = o.run(_ctx())
    assert rec.agent_status["data"] == "failed"
    assert rec.agent_status["demand"] == "skipped"
    assert rec.status == "partial"


def test_single_run_lock() -> None:
    o = Orchestrator()
    o._locked = True
    with pytest.raises(RuntimeError):
        o.run(_ctx())
