# ADR 0001: Feature-based frontend structure

Date: 2026-10-16
Status: Accepted

## Context

The original frontend kept one file per page (`Dashboard.tsx`, `SupplierPage.tsx`,
`ItemPage.tsx`, `explainChat.tsx`) at `src/` root. Shared UI, hooks, utilities, and
the real API shapes were duplicated across pages, with no place for UI primitives,
feature-scoped data fetching, or route-level code splitting.

## Decision

Adopt:

- `src/components/ui/` for shared primitives (`Button`, `Badge`, `Card`, `Table`,
  `Skeleton`, `Modal`, `Toast`, inputs).
- `src/components/layout/` for shell components (`PageShell`) and the route
  `ErrorBoundary`.
- `src/features/<domain>/` for `dashboard`, `suppliers`, `items`, `alerts`, and
  `chat`, each owning its data fetching and presentation.
- `src/hooks/`, `src/lib/`, and `src/types/` for shared behavior, formatting,
  security helpers, and API-matched types.
- TypeScript `@/*` path aliases, wired in both `tsconfig.json` and
  `vite.config.ts`/`vitest.config.ts`.
- Legacy root files (`Dashboard.tsx`, `SupplierPage.tsx`, `ItemPage.tsx`) kept as
  thin re-export shims during migration so existing imports keep working.

## Consequences

- Imports are stable (`@/components/...`, `@/features/...`) instead of fragile
  relative paths.
- Route-level code splitting works because feature modules have explicit exports
  (for example, the dashboard lazy wrapper maps `{ default: m.Dashboard }`).
- The `Supplier`/`Item` shared types now match the real backend shapes
  (`SupplierRow`, `SupplierDetail`, `ItemDetail`) instead of an invented schema.
