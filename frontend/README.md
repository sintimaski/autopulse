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

Core surfaces:

- Overview metrics: requests/minute, error rate, average latency
- Requests and error-group investigation views
- Diagnosis drill-downs and guided troubleshooting
- Alert settings/history and retention/theme settings
- Loading, auth/session, error, and empty-data states
