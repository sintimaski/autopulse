# Frontend Dashboard

This directory contains the Next.js dashboard UI for overview, diagnosis, logs, alerts, and settings.

## Run locally

```bash
npm install
npm run dev
```

Environment variables:

- `NEXT_PUBLIC_LUMONOX_API_BASE_URL` (default: `/lumonox`)

Build modes:

- `LUMONOX_FRONTEND_MODE=static` (default): builds static export for embedding.
- `LUMONOX_FRONTEND_MODE=sidecar`: keeps regular Next runtime output.

Bundle budget guardrails:

- Run `npm run build && npm run check:bundle-budget` to validate route budgets from `.next/diagnostics/route-bundle-stats.json`.
- Current first-load JS budgets: `/dashboard` <= 1000 KiB, `/w/[pageId]` (studio) <= 925 KiB (uncompressed; see `scripts/checkRouteBundleBudgets.mjs`).

Optional frontend RUM (disabled by default):

- `NEXT_PUBLIC_LUMONOX_RUM_ENABLED=1` enables client telemetry capture.
- `NEXT_PUBLIC_LUMONOX_RUM_ENDPOINT=<absolute-or-relative-url>` overrides sink endpoint (default: `/lumonox/rum`).
- `NEXT_PUBLIC_LUMONOX_RUM_SAMPLE_RATE=0.2` samples sessions (0.0-1.0, default `1`).
- `NEXT_PUBLIC_LUMONOX_RUM_DEBUG=1` logs scrubbed payloads to browser console.

Captured fields are intentionally minimal and scrubbed: route path (query/hash removed, id-like segments masked), runtime error message, short stack preview, coarse navigation timing (`dom_content_loaded_ms`, `load_event_ms`), and optional funnel signals (`diagnosis_activation`, `modal_lifecycle`, `filter_zero_results`, `jobs_primary_action`) emitted from `lib/rumRuntime.ts` when sampled.

Core surfaces:

- Overview metrics: requests/minute, error rate, average latency
- Requests and error-group investigation views
- Diagnosis drill-downs and guided troubleshooting
- Alert settings/history and retention/theme settings
- Loading, auth/session, error, and empty-data states

## Architecture (where code lives)

- **`app/`** — Next.js App Router routes and layouts; keep route files thin and delegate UI to `components/dashboard/`.
- **`components/dashboard/`** — Product UI: data provider (`DashboardDataContext`), shell, pages under `dashboardPages/`, charts, scoped query helpers.
- **`components/dashboard/live/`** — Live-update hooks (WebSocket connect, visibility bump, WS-disconnected polling) extracted from the provider to keep `DashboardDataContext.tsx` maintainable.
- **`components/dashboard/data/`** — Slice memo hooks (`useDashboardSlices.ts`) and the **`executeDashboardBatchQuery`** runner for the main `POST /dashboard/query` refresh cycle (invoked from `DashboardDataContext`).
- **`components/ui/`** — Small shared primitives (spinners, etc.) usable from `app/` or dashboard.
- **`lib/`** — Client-only helpers (e.g. RUM) without React dashboard imports.
- **`utils/`** — Pure TS helpers (fetch errors, response shape guards, overview math); safe to unit test in Vitest (`environment: "node"`).

**State boundaries (keep changes predictable):**

| Layer | Owns | Avoid |
| --- | --- | --- |
| **`DashboardDataContext`** | Cross-route dashboard data, scope, orchestrating batch refresh + live bump | Large UI markup; heavy batch logic lives in **`data/executeDashboardBatchQuery.ts`**; settings-only fetches belong in settings hooks |
| **Route / section components** | View-local UI state (open panels, form drafts, table sort) | Duplicating fetch + parse already covered by context or `dashboardSessionFetch` |
| **`utils/`** | Pure parsing, errors, math | React hooks or browser-only globals without guarding SSR |

**Data flow:** Route → `DashboardDataProvider` → page components. Session-scoped dashboard API calls should use **`components/dashboard/dashboardSessionFetch.ts`** (`dashboardSessionFetch`, `dashboardSessionJsonPost`, …) so timeouts and credentials stay consistent (see `DEVELOPMENT.md` / multi-lane plan FE-08). The main overview batch uses **`parseDashboardDataQueryResponse`** in **`utils/dashboardQueryResponseGuards.ts`**; other JSON shapes use **`utils/dashboardResponseGuards.ts`** + `buildDashboardNetworkError` as appropriate.

**When adding features:** Extend existing types in `dashboardTypes.ts`; avoid widening `DashboardDataContext` unless the value is shared across multiple routes.

## Contributor workflow

Recommended before opening a PR (matches repo pre-commit expectations):

```bash
npm run lint
npm run typecheck
npm run test
npm run build
```

Optional: `npm run test:e2e` (requires Playwright browser install: `npx playwright install`). CI runs all specs under `tests/e2e/`, including `dashboard-interaction-smoke.spec.ts` (modal Escape + diagnosis URL scope sync). Bundle size: after `npm run build`, run `npm run check:bundle-budget`.

**Troubleshooting**

- **`npm run typecheck` fails after a merge** — Often a stale `.next` type cache; run `rm -rf .next out` and retry. Ensure imports resolve to `dashboardTypes` / context exports you actually use.
- **`npm run build` fails on static export** — Check `next.config` / `LUMONOX_FRONTEND_MODE`; dashboard routes must stay compatible with the static export path used in CI.
- **ESLint noise** — `eslint.config.mjs` extends `eslint-config-next` and adds a few project rules (`eqeqeq`, `no-debugger`, `import/no-duplicates`, unused-disable directive warnings). Prefer fixing the root cause over blanket `eslint-disable`.
