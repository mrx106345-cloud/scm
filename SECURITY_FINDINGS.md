# SECURITY_FINDINGS.md: Problems Found (Phase 1 close 2026-10-13)

Checklist per section 10 of security-guardrails.md, run at end of phase by the Security reviewer persona. Severity levels per section 11: Critical / High / Medium / Low.

## Phase 0 pre-code review (2026-10-13)
- [x] No secrets in repo, logs, audit payloads, API responses, bundles - None found (docs only; synthetic data).
- [x] Every endpoint has role check; permission tests pass - 33/33 backend tests incl. security unit tests PASS.
- [x] Write paths impossible when write OFF / autonomy level 1 - v1 core is non-write, level-1 default; orchestrator single-run lock prevents partial writes.
- [x] SQL guard + injection cases pass - read-only connector constraints plus unit tests (test_csv_import.py, quality.py).
- [x] Prompt-injection cases pass; no LLM output reaches a tool - v1 LLM is template/mock only (spec section 3); no live LLM.
- [x] Number validator cases pass; template fallback works - number-validator and description (P1-09), template fallback in tests.
- [x] Egress test passes - 2/2 (`backend/tests/security/test_egress.py`): block all outbound connections except loopback.
- [x] Audit chain verifies; tampering detected - audit hash chain unit-tested (test_audit.py).
- [x] Upload/export sanitization tests pass - CSV import formula guard (test_csv_import.py).
- [x] Dependencies audited; licenses recorded - no new dependencies beyond tech-stack.md; offline dev (no lockfile shipped in repo).

## Phase 1 closing (2026-10-13)
Verified:
- Backend suite: 33/33 passed (23 unit + 3 golden + 2 integration + 2 security + 3 skeleton); ruff, mypy, ruff-format clean.
- Acceptance A1-A3 on synthetic data: 200 items A1=0.833, A2=2.276 per 100-item-week, A3=0.785; 5,000 items A1=0.847, A2=2.295, A3=0.815. All thresholds pass.
- Synthetic data seeded (`data/synth/`); demo documented (`docs/demo_phase1.md`); Docker Compose dev environment (`deploy/docker-compose.yml`) and frontend baseline (`frontend/src/Dashboard.tsx`).

Findings:
- None blocking. No secrets in repo or logs. Duplicate ` (1).md` files removed; canonical names authoritative.
- Open: rest of Phases P2-P6 (out of scope; see `BACKLOG.md`) and P1-side follow-ups.
