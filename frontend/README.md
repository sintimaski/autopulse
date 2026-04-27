# Frontend Dashboard (M3 shell)

This directory now contains the M3 dashboard shell implemented with Next.js.

## Run locally

```bash
npm install
npm run dev
```

Environment variables:

- `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` (default: `/autopulse`)
- `NEXT_PUBLIC_AUTOPULSE_API_KEY` (default: embedded local key for one-process mode)

Build modes:

- `AUTOPULSE_FRONTEND_MODE=static` (default): builds static export for embedding.
- `AUTOPULSE_FRONTEND_MODE=sidecar`: keeps regular Next runtime output.

The M3 shell renders:

- Overview metrics: requests/minute, error rate, average latency
- Recent request list: time, method, path, status, latency, service, environment
- Setup, loading, error, and empty-data states
