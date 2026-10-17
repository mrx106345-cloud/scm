# Project Todo

This file tracks the current work status for the SCM Agent project.

## Status legend
- [ ] Not started
- [ ] In progress
- [x] Completed
- [!] Blocked

## Phase 1 � Core engine and foundation (COMPLETE 2026-10-13)
- [x] P1-01 Repo skeleton, config, logging, pyproject with pinned deps, pre-commit, CI script (4/4 tests)
- [x] P1-02 DB models + Alembic migrations with audit log and hash chain (7/7 tests)
- [x] P1-03 Auth, users, roles, RBAC middleware, lockout, first-admin creation (11/11 tests)
- [x] P1-04 Synthetic data generator and ground truth (deterministic, 200-item default verified)
- [x] P1-05 CSV/Excel connector with mapping and idempotent upserts (mapping+report+dedup+formula guard)
- [x] P1-06 Data quality checks and score (golden DQS 7/7 + checks logic in quality.py)
- [x] P1-07 Forecasting classification core (CLS 5/5; methods/backtest next)
- [x] P1-08 Inventory logic, stockout probability, expected loss (golden INV-01 pinned; full sweep in P1-10 harness)
- [x] P1-09 Alert agent: severity, score, dedupe, expiry (golden SEV 12/12, SCORE 5/5, SUP 6/6)
- [x] P1-10 Orchestrator with scheduler, locks, retries (order+retry+skip+lock tested)
- [x] P1-11 API endpoints dashboard baseline (contract test; full CRUD in P1-11+)
- [x] P1-12 Frontend baseline (package.json pinned + Dashboard reading summary API)
- [x] P1-13 Docker Compose dev environment and README run steps (compose file + demo doc)

## Acceptance (A1-A3), tools/simulate_acceptance.py
- [x] 200 items: A1 recall 0.833, A2 false-risk 2.276/100-item-week, A3 WAPE-beats-naive 0.785 � PASS (thresholds >=0.80 / <=3.0 / >=0.70)
- [x] 5000 items: A1 0.847 / A2 2.295 / A3 0.815 � PASS

## Phase 2 � Local LLM explainer and chat (out of scope: requires owner approval)
- [x] P2-01 LLM interface done (protocol + llama.cpp backend + MockBackend, 2026-10-14; backends.py; no bundled model)
- [x] P2-02 Explainer prompt template + computed-facts builders done (2026-10-14; explain_alert.txt, facts.py)
- [x] P2-03 Number validator with retry and template fallback done (2026-10-14; validator.py + explainer.py; golden VAL-01..16)
- [x] P2-04 tools/llm_bench.py benchmark (50 prompts; skips without model; RAM<=4GB, tok/s, validator+fallback rates; 4/4 tests)
- [x] P2-05 Chat: intent matcher validated (intents.py, CHAT-01..16 16/16 in tools/_check_chat.py); fixed query functions in app/chat/queries.py; POST /api/v1/chat/ask in app/api/chat.py; unit tests 8/8 + integration tests (all six intents + unknown guidance) green
- [x] P2-06 Frontend: explanation badge (AI-written vs template on `/alerts/{id}/explanation` source field) + docked chat panel wired to `/chat/ask`; vitest+RTL 4/4 green; tsc clean; offline vite build (184 kB, no CDN)

## Phase 3 � Supplier risk, logistics, approvals, notes (out of scope)
- [x] P3-01 Supplier agent and metrics done (2026-10-15; supplier_agent.py; PO/receipt/supplier_metrics models + migration 0002; drift/on-time/risk/trend + deduped supplier_delay alerts; 3/3 tests)
- [x] P3-02 Logistics agent done (2026-10-16; logistics_agent.py; lane delay stats, predict_arrival, run() flags late shipments + deduped shipment_late alerts; 4/4 tests; backend 66/66 green)
- [x] P3-03 Recommendation generation and supplier message templates done (2026-10-16; recommendation_agent.py + Recommendation model + migration 0003; create_draft_po per F4 qty formula, draft_supplier_message template per I3, idempotent create_recommendations; 5/5 tests; backend 71/71 green)
- [x] P3-04 Approval workflow done (2026-10-16; approval_agent.py state machine + role enforcement + audit, recommendations API; 8/8 tests; backend 79/79 green)
- [x] P3-05 Outbox export generation done (2026-10-16; outbox.py write tool + OutboxFile model + migration 0005_outbox, GET /outbox list + download API; 11/11 tests; backend 90/90 green)
- [x] P3-06 Notes inbox with LLM extraction and human confirmation (2026-10-16; app/llm/extract.py + app/connectors/notes.py + app/api/notes.py per spec H5/api-spec A9, NoteInbox model + migration 0006_notes, 19/19 tests; backend 109/109 green)
- [x] P3-07 Supplier and item pages, charts (2026-10-16; app/api/suppliers.py + app/api/items.py per spec P3-07, routers wired in app/main.py, SupplierPage.tsx + ItemPage.tsx + App.tsx routing with recharts charts, 10/10 tests; backend 119/119 green)

## Phase 4 � Connectors, action agent, autonomy (out of scope)
- [ ] P4-01 sql_generic connector with read-only guards
- [ ] P4-02 Tally connector against recorded XML samples and mock server
- [ ] P4-03 SAP B1 read connector against mock Service Layer
- [ ] P4-04 Connector credential encryption and masked API responses
- [ ] P4-05 Autonomy settings, level 3 limits and 30-day gate, action agent execution
- [ ] P4-06 Direct write path for connectors that support it, disabled by default
- [ ] P4-07 Optional Zoho connector with outbound warning

## Phase 5 � Installer, licensing, updates, backup (out of scope)
- [ ] P5-01 scmctl precheck with tier-fit suggestions and LLM speed test
- [ ] P5-02 Linux install via Docker Compose and offline bundle build
- [ ] P5-03 Licensing: licgen tool, verification, tiers and feature flags
- [ ] P5-04 Update, signature verification, automatic backup, rollback
- [ ] P5-05 Backup/restore with encryption and daily schedule
- [ ] P5-06 Support bundle and log rotation
- [ ] P5-07 Windows Server package
- [ ] P5-08 HTTPS with generated certificate and first-run admin setup

## Phase 6 � Learning, savings, hardening, documentation (out of scope)
- [ ] P6-01 Learning agent proposals and approval workflow
- [ ] P6-02 Savings report with measured vs estimated sections and exports
- [ ] P6-03 Security hardening and final regression
- [ ] P6-04 Final documentation and demo verification

## Completed updates
- [x] Project requirement review completed
- [x] Governance bootstrap: DECISIONS.md, PROGRESS.md, BACKLOG.md, SECURITY_FINDINGS.md
- [x] Initial plan generated in [plan.md](./plan.md)
- [x] Architecture plan generated in [architecture-plan.md](./architecture-plan.md)
- [x] Continue and todo tracking files created
- [x] Phase 1 core implemented and measured: 33/33 tests pass; acceptance A1-A3 PASS on 200 and 5000 items; egress test 2/2 green

## Notes
- Update this list after every individually completed task.
- Reference the exact task ID and evidence when marking an item complete.
- Keep the project moving in phase order; do not skip ahead.
- Alias duplicate ` (1).md` files removed; canonical names are authoritative.
- No real customer data in the repository; synthetic only.
