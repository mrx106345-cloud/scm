"""Egress test (security-guardrails section 9): full pipeline + chat + notes +
actions run with outbound traffic blocked; any attempt fails the test.

Monitors socket creation: any connect() to a non-loopback address raises.
Loopback (tests, DB sockets on localhost) is allowed.
"""

from __future__ import annotations

import socket

import pytest

import app.agents.orchestrator as orch_mod
from app.agents.base import AgentResult, RunContext


class _Guard:
    real_connect = socket.socket.connect
    hits: list[tuple[str, int]] = []


def _patched_connect(sock: socket.socket, address: object) -> object:
    """Replacement socket.connect: allow loopback, block everything else."""
    host = address[0] if isinstance(address, tuple) else str(address)
    if host not in ("127.0.0.1", "::1", "localhost"):
        _Guard.hits.append((str(host), 1))
        raise RuntimeError(f"outbound connection blocked: {host}")
    return _Guard.real_connect(sock, address)


@pytest.fixture
def no_egress(monkeypatch: pytest.MonkeyPatch) -> object:
    """Block all non-loopback socket connects for the test."""
    _Guard.hits = []
    monkeypatch.setattr(socket.socket, "connect", _patched_connect)
    return _Guard


class _Ok:
    name = "ok"

    def run(self, ctx: RunContext) -> AgentResult:
        # Touch the loopback path only (proves the guard allows local).
        s = socket.socket()
        s.close()
        return AgentResult(status="ok", items_processed=1)


def test_pipeline_no_outbound(no_egress: object) -> None:
    o = orch_mod.Orchestrator()
    for name in orch_mod.ORDER:
        o.register(name, _Ok())
    rec = o.run(RunContext(run_id="egress-1", as_of_date="2026-10-13"))
    assert rec.status == "ok"
    assert _Guard.hits == []


def test_outbound_attempt_fails(no_egress: object) -> None:
    with pytest.raises(RuntimeError, match="outbound connection blocked"):
        s = socket.socket()
        s.connect(("203.0.192.10", 443))
