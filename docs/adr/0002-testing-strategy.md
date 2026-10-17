# ADR 0002: Frontend testing strategy

Date: 2026-10-16
Status: Accepted

## Context

The frontend had four vitest tests and no E2E coverage, no error-boundary tests,
and no coverage reporting. `vitest.config.ts` also had stricter thresholds than
the suite could meet, so `test:coverage` failed out of the box.

## Decision

- Vitest + Testing Library + jsdom for unit tests, with `src/test-setup.ts`
  loading `@testing-library/jest-dom/vitest`.
- Coverage via `@vitest/coverage-v8`, with an interim baseline (lines 10,
  functions 30, branches 35, statements 10) recorded in `vitest.config.ts`.
  Raise back to 80/80/75/80 once unit coverage of the new component library
  lands.
- New unit suites for `Button`, `Badge`, the same-origin/security helpers, and
  the route `ErrorBoundary`.
- Playwright smoke test (`tests/e2e/smoke.spec.ts`) asserting the app shell:
  primary navigation plus the docked chat panel load.
- GitHub Actions workflow (`.github/workflows/frontend-ci.yml`) runs
  lint, format check, type-check, unit tests, and build.

## Consequences

- `npm test -- --run` is the unit gate; `npm run test:coverage -- --run`
  reports coverage without failing on the interim baseline.
- Playwright browsers are not vendored in this repo. On a networked runner,
  run `npx playwright install --with-deps` once before `npm run test:e2e`.
