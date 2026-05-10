# Core user journey — browser E2E (Playwright)

Core Playwright smoke lives in `frontend/tests/e2e/core-journey.spec.ts`, `frontend/tests/e2e/settings-smoke.spec.ts`, `frontend/tests/e2e/alerts-smoke.spec.ts`, `frontend/tests/e2e/logs-smoke.spec.ts`, `frontend/tests/e2e/query-explorer-smoke.spec.ts`, and `frontend/tests/e2e/traces-smoke.spec.ts` (shared dev sign-in helper: `frontend/tests/e2e/authDevMagicLink.ts`). Tests run in CI (`browser-smoke` job). This doc is the operator checklist for local maintenance and extension.

## Preconditions

1. Backend running with dashboard auth configured (`backend/.env` from `.env.example`).
2. Frontend dev or production build with `NEXT_PUBLIC_LUMONOX_*` pointing at that API.
3. Test user email allowed for magic link (`DASHBOARD_AUTH_ALLOWED_EMAIL` or domain policy).

## Local run

From repo root:

```bash
uv sync --group dev
npm --prefix frontend ci
npx --prefix frontend playwright install chromium
npm --prefix frontend run build

export DATABASE_URL=sqlite+aiosqlite:///./lumonox_e2e.db
export LUMONOX_EVENT_STORE=duckdb
export LUMONOX_DUCKDB_PATH=./.lumonox/e2e-events.duckdb
export LUMONOX_FRONTEND_STATIC_DIR=frontend/out
export DASHBOARD_AUTH_ENABLED=true
export DASHBOARD_AUTH_ALLOWED_EMAIL=e2e@example.com
export DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN=true
export E2E_BASE_URL=http://127.0.0.1:8000/lumonox/ui
export E2E_DASHBOARD_EMAIL=e2e@example.com

uv run uvicorn lumonox_backend.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
npm --prefix frontend run test:e2e
```

## Covered journey (current smoke)

1. Request dev magic-link token from `/dashboard/auth/magic-link/request`.
2. Verify sign-in via `/lumonox/ui/auth/magic-link?token=...`.
3. Load `/lumonox/ui/dashboard` and assert shell navigation appears (primary links plus an **Advanced** group for query/traces).
4. Navigate to `/lumonox/ui/diagnosis` and assert route + nav stability.
5. Load `/lumonox/ui/settings` and assert primary settings sections render (retention + appearance headings).
6. Load `/lumonox/ui/alerts` and assert the Operations (M5) heading is visible.
7. Load `/lumonox/ui/logs` and assert **Request evidence flow** or the empty-state **No request data for this view** heading.
8. Load `/lumonox/ui/query-explorer` and assert the **Query Explorer** heading and the **SQL query for Query Explorer** field are visible.
9. Load `/lumonox/ui/traces` and assert the **Full tracing (OTLP)** heading is visible.
10. (Optional) Load `/lumonox/ui/diagnosis#grouped-errors` or a saved `#error-group:…` bookmark and confirm the page still renders (deep-link + partial-scope UX is covered in unit tests under `frontend/components/dashboard/diagnosisDeepLink.test.ts`).

Record HAR or video on failure (`trace: 'retain-on-failure'` in config).

## CI wiring (implemented)

- `.github/workflows/ci.yml` job `browser-smoke` builds static frontend export and starts backend with `LUMONOX_FRONTEND_STATIC_DIR=frontend/out`.
- Job waits for `/ready` then runs `npm run test:e2e` in `frontend/`.
- Failures block merges on protected branches.

## Manual smoke (no Playwright)

Use **[docs/ops/PRODUCTION_DEPLOYMENT.md](../ops/PRODUCTION_DEPLOYMENT.md)** §8 plus product walkthrough: sign-in → onboarding → synthetic ingest → diagnosis → alert test dispatch.
