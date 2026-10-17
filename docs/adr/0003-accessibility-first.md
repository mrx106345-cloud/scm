# ADR 0003: Accessibility and offline security baseline

Date: 2026-10-16
Status: Accepted

## Context

The UI had no error boundaries, no enforced Content Security Policy, and no
guard against rendering external/injected URLs as API endpoints, despite the
hard rule that the product runs fully offline with synthetic data only.

## Decision

- Wrap the app shell and every route (plus the docked chat panel) in an
  `ErrorBoundary` with a `role="alert"` fallback and one-click reload.
- Ship a same-origin CSP meta tag in `frontend/index.html`
  (`default-src 'self'`, scripts/styles/images/fonts/connect all pinned to self,
  `object-src 'none'`).
- Add `src/lib/security.ts` helpers: `isSameOriginApiPath`,
  `assertSameOriginApiPath`, and `escapeHtml`, with unit tests.
- Replace the `@headlessui/react` modal dependency with a dependency-free,
  keyboard-dismissable dialog (`Escape` closes, body scroll is locked).
- Add `aria-label="Primary"` to the app nav and `aria-modal`/`aria-label` to
  the modal; keep `eslint-plugin-jsx-a11y` recommended rules on.
- Remove `date-fns` and `currency.js` usages in favor of dependency-free
  `Intl` formatters so no new runtime dependency is needed.

## Consequences

- Production builds keep working with no CDN and no new install footprint.
- Future mutations must route through same-origin `/api/*` paths and render
  server text as text, never as executable markup.
