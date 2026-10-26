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

## Frontend dependency audit (2026-10-17)

Run as Security reviewer after the vitest 5 / vite 6.4 toolchain upgrade (`npm audit` in `frontend/`).

Findings (original report: 5 vulnerabilities — 3 high, 2 moderate):
- **HIGH** `braces` stack-exhaustion DoS via deeply nested patterns (GHSA-vfj7-8cjw-p6xm), reached through `micromatch <- lint-staged 15.5.2` (dev-only: pattern matching runs at commit time on staged paths). Fixed by upgrading `lint-staged -> 17.6.0` (requires Node >=22.22.1; repo runs Node 24.19.0).
- **HIGH** `react-router` XSS via same-origin redirect starting `//` (GHSA-2w69-qvjg-hvjx, GHSA-2j2x-hqr9-3h42) - reached through `react-router-dom 6.28.0` (**runtime** dependency).
- **MODERATE** `react-router` open redirect via backslash in `<Link>`/`useNavigate` (GHSA-wrjc-x8rr-h8h6) and arbitrary constructor injection via `deserializeErrors()` in SSR hydration (GHSA-337j-9hxr-rhxg). **No 6.x fix exists** — the vulnerable range is `>=6.0.0 <=7.17.0`.

Remediation:
- `react-router-dom 6.28.0 -> 6.30.6` first cleared the two HIGH redirect advisories; the remaining two MODERATE advisories had no v6 patch, so upgraded **`react-router-dom -> 7.18.4`** (peer `react >=18` satisfied by 18.3.1). App usage is the v7-stable surface only (`BrowserRouter`, `Routes`, `Route`, `Link`, `NavLink`, `useParams`) — verified by new `src/router.test.tsx` (4 tests: route matching, path params, Link navigation, NavLink active state).
- `lint-staged 15.5.2 -> 17.6.0`.
- Re-run: **`npm audit` = 0 vulnerabilities (exit 0)**.

Notes: the `deserializeErrors` advisory targets SSR hydration; this app is CSR-only (`BrowserRouter`), so exposure was theoretical — still cleared. The Zoho/egress posture is unchanged (no new network surface; router is a pure client-side path library). CI does not yet run `npm audit`; consider adding it to `frontend-ci.yml`.\n

## Security-hardening review (2026-10-26, branch `security-hardening`)

Full-project review found real perimeter gaps; the following were fixed and
pinned with tests on the branch:

- **HIGH - login password mismatch on multi-dialect bodies / no lockout
  wiring.** Login accepted form/query passwords with no lockout enforcement
  and no audit events. Fixed: JSON body only, LockoutTracker (5 failures /
  sliding 15-min) -> 429, every outcome audited (`auth.login`,
  `auth.login_failed` with reason, `auth.bootstrap_admin`, `auth.logout`).
  Pinned by `backend/tests/unit/test_auth_flow.py` (13 tests, real deps).
- **HIGH - CSRF not enforced app-wide.** Only login/logout checked; all other
  mutating endpoints were cookie-attackable. Fixed: `verify_csrf` dependency
  on every router.
- **HIGH - endpoints mounted but editable by wrong/no role.** chat,
  catalog, suppliers, notes, outbox, recommendations mutated/read without
  enforced minimum roles; missing role defaulted to viewer. Fixed: explicit
  `require_role(...)` per permissions-map.yaml; missing role DENIES.
- **MEDIUM - disabled-account state leak.** `/auth/login` reported disabled
  before verifying the password. Fixed: password verified first; generic 401
  for wrong password.
- **MEDIUM - prod session secret fail-fast missing.** `SCM_ENVIRONMENT=prod`
  plus built-in dev secret now refuses to boot (model_validator).
- **MEDIUM - outbox exported pre-edit numbers.** edit_approve decisions were
  exported from the original payload. Fixed: outbox uses `edited_payload`;
  approval_agent validates edited JSON at decision time (400).
- **MEDIUM - unknown supplier filter matched ALL alerts.** Chat `list_alerts`
  supplier filter with no matching supplier returned every alert (info
  disclosure). Fixed: `in_` on empty id list -> zero rows.
- **LOW - prompt-injection fence escape gaps.** Notice text containing fence
  markers could break the fence. Fixed: regex now catches open/close (incl.
  slashed variants) inside notice content.
- **LOW - frontend same-origin check was leading-slash only.** `//evil.com/x`
  passed. Fixed allowlist `/^(api|auth)/`; auth client routes through the
  same-origin client with CSRF + global 401 redirect.
- **LOW - dev SQLite DB (backend/scm_dev.db) tracked in git.** Untracked +
  gitignored (`*.db`/`*.sqlite*`); binary artifacts do not belong in the
  repo even when synthetic (regenerated; unrecoverable diff noise).

Gates on the branch: backend 173/173 (incl. 13 new auth-flow tests), ruff +
format + mypy(app, strict) clean; frontend 93/93, lint/format/type-check/
build clean; npm audit 0 vulnerabilities (pruned unused zod HIGH); bandit
app/ 0 findings. CI: pip install fixed (setuptools packages.find), pip-audit +
bandit steps added; frontend-ci node 22 + coverage + audit.

Open items for the owner (NOT fixed here; schema/formula/contract changes
require approval per agents.md):
1. Connectors-phase security review (P4 sql_generic/Tally/SAP) never ran at
   phase end - schedule one when the phase lands (this entry starts closing
   the gap for the shared read-only core, which has unit tests + bandit).
2. Money as Decimal in columns (currently float NUMERIC columns).
3. Unique constraints: alerts.dedupe_key dedupe relies on the upsert flow;
   audit chain needs an append-only uniqueness policy.
4. Orchestrator single-run lock is advisory in-process; DB advisory lock for
   multi-process deployments.
5. Timezone-aware columns + absolute session timeout (jti revocation list).
6. Full A4 alert list shape (needs alert fact columns) - list endpoints
   remain authenticated empty stubs pending approval.
7. Data-quality persistence (dashboard DQ score placeholder 0).
8. SAP host allowlist config key.
9. Pinned vs modern toolchain + lockfile (local/CI drift; Python
   >/3.13 not supported by the backend's requires-python until pinned).
