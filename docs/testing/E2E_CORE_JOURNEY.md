# Core user journey — browser E2E (Playwright)

Automated browser coverage is optional today (Vitest handles most dashboard logic). Use this checklist when adding **Playwright** in CI or before a major release.

## Preconditions

1. Backend running with dashboard auth configured (`backend/.env` from `.env.example`).
2. Frontend dev or production build with `NEXT_PUBLIC_AUTOPULSE_*` pointing at that API.
3. Test user email allowed for magic link (`DASHBOARD_AUTH_ALLOWED_EMAIL` or domain policy).

## Install Playwright (frontend)

From `frontend/`:

```bash
npm install -D @playwright/test
npx playwright install
```

Add `frontend/playwright.config.ts` with `baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:3000'`.

## Minimal journey (script outline)

1. `page.goto('/auth/magic-link')` — request link for allowed email (or use dev token flow in non-prod).
2. Complete sign-in (dev link or test inbox integration).
3. Assert redirect to `/onboarding` or `/dashboard` per onboarding state.
4. `page.goto('/dashboard')` — overview charts or loading boundary visible.
5. `page.goto('/diagnosis')` — grouped errors section present.
6. `page.goto('/alerts')` — settings card visible.
7. `page.goto('/requests')` — table or empty state without crash.

Record HAR or video on failure (`trace: 'retain-on-failure'` in config).

## CI wiring (suggested)

- Job sets `E2E_BASE_URL`, starts backend + `npm run start` for frontend, waits on `/ready`.
- Run `npx playwright test` with **shard** parallelization if the suite grows.

## Manual smoke (no Playwright)

Use **[docs/ops/PRODUCTION_DEPLOYMENT.md](../ops/PRODUCTION_DEPLOYMENT.md)** §8 plus product walkthrough: sign-in → onboarding → synthetic ingest → diagnosis → alert test dispatch.
