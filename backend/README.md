# AutoPulse Backend

FastAPI backend for ingest, dashboard APIs, auth/session flows, alerts, retention jobs, and realtime updates.

## What lives here

- Ingest API: `POST /ingest` with API-key authentication.
- Dashboard API: overview, requests, error groups, diagnosis, alerts, settings, log query, organizations.
- Dashboard auth: magic-link sign-in, cookie sessions, tenant bootstrap endpoint.
- Background jobs: alert evaluation and retention cleanup.
- Internal ops endpoints: health/ready and service metrics.

## Run locally

From repository root:

```bash
uv sync --group dev
uv run python -m autopulse_backend.main
```

Backend defaults to `http://localhost:8000`.

## Key environment variables

- `DATABASE_URL`
- `CORS_ALLOW_ORIGINS`
- `DASHBOARD_AUTH_ALLOWED_EMAIL`
- `DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN` (dev-only convenience; default is disabled)
- `DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK` (disabled by default; enable only for controlled non-browser flows)
- `INGEST_MAX_REQUEST_BYTES`
- `INGEST_RATE_LIMIT_REQUESTS_PER_WINDOW`
- `INGEST_RATE_LIMIT_WINDOW_SECONDS`
- `INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED` (enables DB-backed distributed limiter)
- `INGEST_ASYNC_AGGREGATE_ENABLED` (keeps ingest hot path raw-write-first)
- `INGEST_ASYNC_AGGREGATE_QUEUE_MAX_SIZE`
- `JOBS_ENABLE_SCHEDULER`
- `JOBS_SCHEDULER_LEASE_ENABLED` (prevents duplicate periodic job execution across instances)
- `JOBS_SCHEDULER_LEASE_TTL_SECONDS`

See `backend/src/autopulse_backend/core/config.py` for the complete list and defaults.

## Operational runbooks

- Alert delivery setup and verification: `backend/ALERT_DELIVERY_RUNBOOK.md`
- Release/incident drill gates: `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md` and `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`

## Scope and constraints

Product/architecture source of truth remains `DEVELOPMENT.md`.
