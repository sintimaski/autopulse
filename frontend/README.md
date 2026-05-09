# Frontend Dashboard

This directory contains the Next.js dashboard UI for overview, diagnosis, logs, alerts, and settings.

## Run locally

```bash
npm install
npm run dev
```

Environment variables:

- `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` (default: `/autopulse`)

Build modes:

- `AUTOPULSE_FRONTEND_MODE=static` (default): builds static export for embedding.
- `AUTOPULSE_FRONTEND_MODE=sidecar`: keeps regular Next runtime output.

Bundle budget guardrails:

- Run `npm run build && npm run check:bundle-budget` to validate route budgets from `.next/diagnostics/route-bundle-stats.json`.
- Current first-load JS budgets: `/dashboard` <= 975 KiB, `/widgets-showcase` <= 925 KiB (uncompressed).

Optional frontend RUM (disabled by default):

- `NEXT_PUBLIC_AUTOPULSE_RUM_ENABLED=1` enables client telemetry capture.
- `NEXT_PUBLIC_AUTOPULSE_RUM_ENDPOINT=<absolute-or-relative-url>` overrides sink endpoint (default: `/autopulse/rum`).
- `NEXT_PUBLIC_AUTOPULSE_RUM_SAMPLE_RATE=0.2` samples sessions (0.0-1.0, default `1`).
- `NEXT_PUBLIC_AUTOPULSE_RUM_DEBUG=1` logs scrubbed payloads to browser console.

Captured fields are intentionally minimal and scrubbed: route path (query/hash removed, id-like segments masked), runtime error message, short stack preview, coarse navigation timing (`dom_content_loaded_ms`, `load_event_ms`), and optional funnel signals (`diagnosis_activation`, `modal_lifecycle`, `filter_zero_results`, `jobs_primary_action`) emitted from `lib/rumRuntime.ts` when sampled.

Core surfaces:

- Overview metrics: requests/minute, error rate, average latency
- Requests and error-group investigation views
- Diagnosis drill-downs and guided troubleshooting
- Alert settings/history and retention/theme settings
- Loading, auth/session, error, and empty-data states
