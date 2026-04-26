# Frontend Dashboard (M3 shell)

This directory now contains the M3 dashboard shell implemented with Next.js.

## Run locally

```bash
npm install
npm run dev
```

Environment variables:

- `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` (default: `http://localhost:8000`)
- `NEXT_PUBLIC_AUTOPULSE_API_KEY` (required for authenticated dashboard reads)

The M3 shell renders:

- Overview metrics: requests/minute, error rate, average latency
- Recent request list: time, method, path, status, latency, service, environment
- Setup, loading, error, and empty-data states
