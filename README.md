# SCM Agent

On-premise, fully offline AI supply chain risk system for mid-size manufacturers.
Spec: `DEVELOPMENT_SPEC_scm_agent.md`. Progress: `PROGRESS.md`. Decisions: `DECISIONS.md`.

## Status (2026-11-04) — Phases 1-3 + ERP read connectors implemented; CI/e2e green

- **Tests:** backend 173/173 green (unit, integration, security, golden inventory 11/11 cases, golden alerts/classify); frontend 93/93 Vitest tests in 18 files; Playwright e2e 2/2 chromium smoke tests (ran for the first time 2026-11-04).
- **CI:** GitHub Actions `ci` (Python 3.11: install/lint/mypy/pytest/bandit/pip-audit) and `frontend-ci` (node 22: lint, format, types, unit tests, coverage, audit, build, Playwright smoke) both green on `main`. The previous persistent `ci` failure was a phantom `mypy==1.13.2` pin (never published on PyPI; fixed 2026-11-04).
- **Lint/types:** ruff clean, ruff format clean, mypy `app` clean (strict, 55 files). Frontend lint/format/type-check clean.
- **Security-hardening (2026-10-26):** JSON-body login with lockout + full `auth.*` audit trail, RBAC deny-by-default on every router, CSRF header dependency app-wide, prod-secret fail-fast, live-ledger dashboard summary, outbox honors edited payloads, prompt-injection fence hardening, frontend auth client with same-origin hardening + global 401 redirect. See `SECURITY_FINDINGS.md`.
- **Acceptance (A1-A3)** on synthetic data, `tools/simulate_acceptance.py`:
  - 200 items: A1 recall 0.833 (40/48 event-caused stockout detected), A2 false-risk 2.276 per 100 items per week (threshold <=3.0), A3 WAPE-beats-naive 0.785 (threshold >=0.70) — PASS.
  - 5,000 items: A1 0.847 / A2 2.295 / A3 0.815 — PASS.
- **Egress test** (no outbound connections by default): 2/2 pass (`backend/tests/security/test_egress.py`).
- **Data seeded:** `data/synth/` canonical CSVs + `ground_truth.json` (200 items, 2 sites, 25 suppliers).
- **Dev stack:** `deploy/docker-compose.yml` (PostgreSQL 16 + api; the scheduler/worker service arrives with the pipeline-cron phase).

## Run

Setup:
```bash
pip install -e ./backend[dev]
pytest ./backend -q
ruff check ./backend
mypy ./backend/app

# API (uvicorn; scheduler/worker lands with the pipeline-cron phase)
docker compose -f deploy/docker-compose.yml up --build
```

Frontend (React 18 + TS + Vite, all assets bundled - no CDN, no external API):
```bash
cd frontend
npm install

npm run dev            # dev server, proxies /api -> 127.0.0.1:8000
npm run lint           # ESLint 9 flat config (React + hooks + jsx-a11y + TS)
npm run format:check   # Prettier gate (npm run format:write to fix)
npm run type-check     # tsc --noEmit (strict)
npm test -- --run      # Vitest unit tests (93 tests, 18 files)
npm run test:coverage  # Vitest + V8 coverage (interim thresholds; raise toward 80%)
npm run build          # tsc + vite build (route-split Dashboard chunk)
npm run test:e2e       # Playwright smoke (once: `npx playwright install`, networked runner)
```

Frontend layout: `src/features/{dashboard,suppliers,items,alerts,chat}` (feature-scoped pages and data fetching), `src/components/ui` (shared primitives: Button, Badge, Card, Table, Modal, Toast, inputs), `src/components/layout` (PageShell, route `ErrorBoundary`), `src/hooks`, `src/lib` (dependency-free Intl formatters, `cn`, security helpers), `src/types` (API-matched shapes). Path alias `@/*` maps to `src/*` in tsconfig, vite, and vitest. CI: `.github/workflows/frontend-ci.yml` runs lint, format, type-check, unit tests, build. ADRs: `docs/adr/0001`-`0003`.

## Phases
| Phase | Scope | Status |
|---|---|---|
| P1 core engine & foundation (currently) | models, audit, auth/RBAC, synth, import, quality, forecast, inventory, alerts, orchestrator, API, frontend, compose | **complete** (2026-10-13) |
| P2 Local LLM explainer & chat | explanation UI, number validator, llm_bench | **implemented** (see `PROGRESS.md`; model file deferred) |
| P3 Supplier risk, logistics, approvals | suppliers, logistics, approvals, outbox, notes | **complete** (2026-10-16, see `PROGRESS.md`) |
| P4 Connectors & action agent | sql/Tally/SAP read-only, autonomy | **P4-01..03 connectors implemented** (2026-10-23, see `todo.md`); credential encryption, action agent/autonomy pending |
| P5 Installer, licensing, updates, backup | precheck, installer, license, backup | not started |
| P6 Learning, savings, hardening, docs | savings, security review, final documentation | not started |

All P1 acceptance thresholds (A1 >= 0.80, A2 <= 3.0, A3 >= 0.70) measured and met. Phase 4 action agent/autonomy, Phase 5 and Phase 6 remain (see `todo.md`); further PRD non-goals are parked in `BACKLOG.md`.

## Notes
- Alias files like `agents (1).md` removed; canonical names are authoritative.
- Do not edit `evaluation-dataset.json`, `permissions-map.yaml`, or `security-guardrails.md` without owner approval.
- Synthetic data only. No real customer data.
