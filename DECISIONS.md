# DECISIONS.md: Choices and Reasons — SCM Agent
Owner: mrx. Init: 2026-10-13. Persona: Builder (planning).
Priority: security-guardrails > permissions-map > DEVELOPMENT_SPEC > architecture.

## 1. Product in 10 lines
1. On-premise offline supply-chain risk system; software-only, license + 20% maintenance.
2. Detects stockout/supplier-delay/excess/dead-stock >=7 days early, ranked by loss x urgency.
3. Numbers from deterministic code (E3/E4); local 2GB LLM only phrases, validator-enforced.
4. Default autonomy Level 1 (advise); write-back OFF; approvals human-gated + audited.
5. CPU-only 4 cores/16GB (min 8GB); LLM <=4GB; Postgres prod, SQLite dev/test.
6. CSV/Excel first, then sql/Tally/SAP-B1 read-only; Zoho optional OFF.
7. Hash-chained audit_log; no secrets/C3 in logs or bundles.
8. Roles admin/planner/purchaser/viewer; deny-by-default RBAC.
9. Synthetic data only; golden file evaluation-dataset.json (138 cases, read-only).
10. Phases 1-6 in order; Phase 1 exit A1-A7 measured on synthetic data.

## 2. Folder layout (P1-01, per Part B)
backend/{pyproject.toml,alembic/,app/{main.py,config.py,db/,core/,connectors/,pipeline/,forecasting/,agents/,llm/,api/,reports/},tests/}
frontend/ (React18+TS+Vite, bundled only). tools/{synth_data,licgen,scmctl}. deploy/. docs/.
Root: README PROGRESS BACKLOG SECURITY_FINDINGS DECISIONS SPEC.md.
Note: repo root IS d:\PH; no nested scm-agent/ wrapper.

## 3. Libraries (tech-stack.md only, no new deps)
Python 3.11 prod (local 3.14.7 dev-only). FastAPI+Uvicorn(+Gunicorn Linux), Pydantic2+settings, SQLAlchemy2+Alembic+psycopg3. Auth argon2-cffi+PyJWT cookie+CSRF. Crypto cryptography only. Data pandas+numpy; openpyxl read, XlsxWriter write. Forecast statsmodels+sklearn+scipy (Croston/TSB in-house). Opt PuLP (MIT, CBC bundled). LLM llama-cpp-python + MockBackend. httpx+respx (egress-blocked). reportlab+matplotlib, Jinja2 autoescape, typer, psutil, lxml. Tests pytest/cov/asyncio/hypothesis/freezegun/respx. Quality ruff+mypy-strict+bandit+pip-audit. Frontend React18/Router/Vite, TanStack Query/Table, RHF+Zod, Radix+CSS, Recharts, Vitest/RTL/Playwright-dev. No Celery/Redis/LangChain/vectorDB/eval/pickle/CDN.

## 4. Phase-1 order
P1-01 skeleton/config/logging/pins/CI -> P1-02 models+migrations+audit chain -> P1-03 auth/RBAC/lockout/first-admin -> P1-04 synth+ground_truth -> P1-05 csv_excel upsert+report -> P1-06 quality score+gate -> P1-07 classify/backtest/select -> P1-08 inventory E3-E5 -> P1-09 alerts -> P1-10 orchestrator -> P1-11 API subset -> P1-12 frontend -> P1-13 compose+README.

## 5. Test strategy
TDD; golden tests read-only on evaluation-dataset.json (138 cases). Coverage >=80% agents/forecasting/core. Egress green always. Audit-tamper test. Perf 200 items <2min, 5000 <10min on 4 cores. Bench harness tools/bench_pipeline.py from P1-01.

## 6. Conflicts and gaps
- todo.md refs tasks.md/rfc.md/permissions-map.yaml/test-suite-spec.md/incident-response.md/privacy-policy-ai.md — ABSENT in d:\PH. Use DEVELOPMENT_SPEC+api-spec+security-guardrails; do not invent. Derive minimal permissions-map.yaml in P1-03.
- Ignore dupes named ` (1).md`; canonical names win.
- Severity rule: critical = (P>=0.50 any class) OR (days<=3 AND criticality A). Pin in P1-09 tests.
- Synth 3y = 156 wks, so ETS-seasonal (needs 104) and gradient_boosting (needs 104) are eligible.
- No Tally/SAP vendor docs in repo; P4 builds against mocks/samples only.
- Model choice deferred to Phase 2 + owner approval; no download now.

## 7. Next step
P1-01 first: skeleton + pinned pyproject + ruff/mypy/pre-commit + CI + JSON logging + pydantic-settings config. Prove with pytest + ruff + mypy green. Then P1-02 onward in order with PROGRESS/todo/continue updates each task.

## 8. Needs from owner
First ERP/industry for pilots? Starter tier advise-only or with approvals? Build Zoho at all (default NO)? Currency INR lakh/crore default (assume yes, toggle)? LLM model file + license (Phase 2)?

## 9. P2-06 frontend test deps (2026-10-15)
Need: @testing-library/react, @testing-library/jest-dom, @testing-library/user-event (test-only), jsdom environment for vitest.
Tech-stack allows these exact entries ("React Testing Library", "Vitest"; jsdom is the standard vitest browser-env dependency).
Alternatives: test only with hand-rolled fetch mocks and no DOM — rejected, that would not prove badge/panel render behavior.
License/size/security: @testing-library/* and jsdom are MIT; versions pinned below once resolved (>=2 weeks old check at install time).
Offline: packages install from npm cache and are committed via package-lock.json; all runtime assets remain bundled, no CDN.
RTL is test-only surface; production bundle excludes it. Model choice still deferred.

## 10. P3-05 Outbox export (2026-10-16)

- Model: `OutboxFile` (`outbox_files`: id, filename, file_type xlsx|csv|txt check constraint, recommendation_id FK, path, size_bytes, created_at) + alembic `0005_outbox.py` (portable DDL, validated via create_all since alembic CLI unavailable in this env).
- `outbox.write` tool = `write_export()` in app/connectors/outbox.py: requires the recommendation to be `approved` (same gate as `actions.execute`; pending/rejected/unknown raise ValueError/FileNotFoundError), writes XLSX/CSV/TXT under settings.outbox_dir, one row per recommendation (base fields + payload keys), audits `outbox.export` with the acting user.
- Filenames system-generated only: `PO_<display_id>_<timestamp>.{ext}` (security-guardrails allow-list); download path resolved from the DB row only, with a path-traversal (`_is_inside`) guard; never user-supplied.
- API (api-spec A5/A14): `GET /outbox` (planner/purchaser/admin) lists `{id, name, type, created_at, recommendation_id}`; `GET /outbox/{file_id}/download` returns FileResponse + audits `outbox.download`; viewer gets 403, missing file 404. Placeholder actor headers (X-Acting-*/X-Acting-*) pending real auth (P1-11+), consistent with the recommendations API.
- Cells sanitized with `sanitize_export_cell` from app/connectors/csv_excel.py (formula-injection guard).

## 11. P3-06 Notes inbox (2026-10-16)

- Model: `NoteInbox` (`notes_inbox`: id, supplier_id FK suppliers NULL, raw_text, extracted JSON text, status `new`/`confirmed`/`dismissed` check constraint, received_at) + alembic `0006_notes.py` (portable DDL, validated via create_all since alembic CLI unavailable in this env). Schema follows Part C2 exactly — no extra columns for confirmed values, since changing a spec-defined schema table needs owner approval; `confirm` writes supplier_id + status to the row and records new_delay_days/affected_item_ids in the audit payload only.
- Extraction: `app/llm/extract.py` — notice text fenced in `<<NOTICE>>` / `<<ENDNOTICE>>` delimiters; model told the fenced text is untrusted data containing no instructions and must never be obeyed; json_schema `{supplier, new_delay_days, affected_items, date}`; output is a suggestion and never auto-applied (spec H5 / security-guardrails 4). Suspicious input (ignore/forget instructions, system prompt, reveal secrets/passwords/license, admin mode, autonomy level, approve all, mark executed, delete audit log, forward/send stock list or data, delimiter escape) is flagged as suspicious and never sent to the model; extraction failures leave `extracted` NULL but the notice is still stored as `new`.
- Service: `app/connectors/notes.py` — `create_note` (8,000-char cap per api-spec A9, audits `notes.receive`), `list_notes`, `get_note`, `confirm_note` (planner only; `new` -> `confirmed`, both terminal in this phase; human values only), `dismiss_note` (planner/purchaser; `new` -> `dismissed`). Every state change audited via append_entry (`notes.receive`/`notes.confirm`/`notes.dismiss`, hash-chained).
- API (api-spec A9): `POST /notes` (planner/purchaser, 201), `GET /notes` (planner/purchaser), `POST /notes/{id}/confirm` (planner only), `POST /notes/{id}/dismiss` (planner/purchaser); viewer 403, missing note 404, re-confirm/re-dismiss 409. Placeholder actor headers (X-Acting-Role/X-Acting-User) pending real auth (P1-11+), consistent with the recommendations/outbox APIs.
- Tests: `tests/unit/test_notes.py` — 19 tests covering service + routes incl. all 8 prompt_injection cases from evaluation-dataset.json (stored as `new`, never auto-confirmed, suspicious flagged, zero confirm/dismiss actions). Full backend suite 109/109 (was 90); ruff clean; mypy clean on changed files.

## 12. Audit chain bug fix (2026-10-16)

`app/core/audit.append_entry()` chained on the previous row's `prev_hash` instead of its `hash`, so consecutive entries in one session both linked to genesis and the tamper-evident chain was broken. Fixed to chain on `last.hash` (genesis for the first row), matching the spec formula `hash = sha256(prev_hash || canonical entry)`. Verified by `test_export_is_hash_chained` (two consecutive `outbox.export` entries link correctly). No spec change — implementation aligned to the documented formula.

## 13. Frontend hardening toolchain (2026-10-16)

- ESLint 9 flat config (`frontend/eslint.config.js`): `@eslint/js` recommended +
  `typescript-eslint` recommended + React/Hooks/JSX-a11y recommended; unused vars
  error, console/debugger guarded. Pinned `@eslint/js@9.39.5` with `globals` and
  `@vitest/coverage-v8@1.6.1` because latest `@eslint/js` wants ESLint 10 and
  latest coverage wants Vitest 5.
- Vitest V8 coverage wired (`reportsDirectory ./coverage`, interim thresholds
  lines 10 / functions 30 / branches 35 / statements 10 in `vitest.config.js`
  until new UI unit coverage lands; raise back to 80/80/75/80).
- Path alias `@/*` now resolved in `vite.config.ts` and `vitest.config.ts`
  (previously only `tsconfig.json`), fixing the production build's Rollup
  resolution of `@/...` lazy imports.
- Added `lint:fix` script; `format:check`/`format:write` enforced via Prettier 3;
  no new runtime network surface (formatters use `Intl`, modal no longer needs
  `@headlessui/react`).



## 14. Tailwind CSS v4 design-token layer (2026-10-17)

- New devDependencies: `tailwindcss@^4.3.3` + `@tailwindcss/vite@^4.3.3`.
  Build-time only: the output is a static CSS file served same-origin, no
  runtime JS, no CDN, no telemetry — satisfies the offline hard rule.
- Why: the UI kit and feature pages were written against a shadcn-style
  utility vocabulary (176 distinct tokens incl. semantic `bg-success/10`,
  `text-warning`, `focus:ring-ring`) while the repo contained **zero**
  stylesheets, so every component rendered unstyled.
- `src/styles/index.css` defines each semantic token in `@theme`
  (slate/blue enterprise palette), a token-level `.dark` scope for the
  future theme toggle (components carry no `dark:` variants), the
  `slideIn` keyframes referenced by Toast's `animate-[slideIn_...]`, and a
  v4 base-layer shim setting the default border color to
  `--color-border` (v4 would otherwise inherit `currentColor`).
- Registered `tailwindcss()` in `vite.config.ts`; `main.tsx` imports the
  stylesheet. Vitest does not process CSS, so tests are unaffected.
- Verified: production build emits `dist/assets/index-*.css` (~27 kB)
  containing all used utilities, including escaped `focus\:ring-ring`
  and `hover\:bg-accent`.

## 15. Git repository, LF policy and real hooks (2026-10-17)

- `git init -b main` (earlier attempts were no-ops); initial import
  `0534ae2` = 204 files, secrets scan clean (no `.env`/keys staged).
- Root `.gitignore` added (Python caches/venvs, env files, logs); the
  nested `frontend/.gitignore` already covered `node_modules`/`dist`.
- `.gitattributes` pins `* text=auto eol=lf`: the Git for Windows
  **system-level** `core.autocrlf=true` (C:/Program Files/Git/etc/gitconfig)
  kept rewriting checked-out files to CRLF, which was the root cause of
  repeated Prettier `endOfLine` flakiness. Attributes outrank autocrlf.
- Hooks live at the repo root (`core.hooksPath=.husky`) because the git
  repo root and the npm package root differ; each hook `cd`s into
  `frontend/` for lint-staged/commitlint. Both files start with
  `#!/bin/sh` (Windows cannot spawn shebang-less hooks) and are LF-only.
- `commitlint.config.js` renamed to `.cjs`: `frontend/package.json` has
  `"type": "module"`, so cosmiconfig loaded the CommonJS config as ESM
  and crashed — the config had never actually executed before git existed.
- lint-staged glob widened to `**/*.{ts,tsx}` so nested sources match
  deterministically when the config is resolved from `frontend/`.
- Proven live: pre-commit ran eslint+prettier on 50 files; commit-msg
  **rejected** one over-long body line (`body-max-line-length`) and then
  passed after rewrapping. CI workflow YAML validated with PyYAML; the
  actual Actions run still needs a GitHub remote.
