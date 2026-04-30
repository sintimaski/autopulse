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
# Loads backend/.env so retention/cap settings are actually applied.
uv run uvicorn autopulse_backend.main:app --env-file .env --log-level info
```

Backend defaults to `http://localhost:8000`.

## Key environment variables

- `DATABASE_URL`
- `CORS_ALLOW_ORIGINS`
- `DASHBOARD_AUTH_ALLOWED_EMAIL`
- `DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK` (disabled by default; enable only for controlled non-browser flows)
- `INGEST_MAX_REQUEST_BYTES`
- `INGEST_RATE_LIMIT_REQUESTS_PER_WINDOW`
- `INGEST_RATE_LIMIT_WINDOW_SECONDS`
- `INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED` (enables DB-backed distributed limiter)
- `INGEST_ASYNC_AGGREGATE_ENABLED` (keeps ingest hot path raw-write-first)
- `INGEST_ASYNC_AGGREGATE_QUEUE_MAX_SIZE`
- `INGEST_DROP_AUTOPULSE_TRAFFIC_FROM_DB` (drops `/autopulse/*`, `/dashboard/*`, and `/ingest` events before persistence)
- `JOBS_ENABLE_SCHEDULER`
- `JOBS_RETENTION_INTERVAL_SECONDS` (minimum **5**; periodic `run_retention_cleanup_once` when scheduler or retention-only loop runs)
- `JOBS_SCHEDULER_LEASE_ENABLED` (prevents duplicate periodic job execution across instances)
- `JOBS_SCHEDULER_LEASE_TTL_SECONDS`
- `AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB` (max SQLite **disk** footprint in MB for main + `-wal` + `-shm`; unset on default `autopulse.db` / `autopulse_embedded.db` defaults to **512**; retention deletes oldest data then VACUUM)
- `AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS` / `AUTOPULSE_RETENTION_PRESSURE_MIN_INTERVAL_SECONDS` (SQLite pressure poll; see `core/config.py`)

See `backend/src/autopulse_backend/core/config.py` for the complete list and defaults.

## Retention scheduling (FastAPI-optional)

The portable unit of work is **one retention pass** (SQLite caps, time windows, aggregates trim):

| How | Command / API |
|-----|-----------------|
| **CLI (any OS, no web server)** | `cd backend && uv run python -m autopulse_backend.jobs retention-once` |
| **Sync Python (cron, Django command, systemd `ExecStart`)** | `from autopulse_backend.jobs import run_retention_sync` then `run_retention_sync()` after setting `DATABASE_URL` in the environment |
| **In-process (FastAPI)** | Lifespan starts the scheduler or retention-only loop; optional SQLite pressure poll |

For **Linux production** or **Django** (no FastAPI event loop), prefer **cron** or **systemd timers** calling the CLI or `run_retention_sync()` on the interval you want, and set `JOBS_ENABLE_SCHEDULER=false` on the API so you do not double-run retention in-process and from cron.

Example cron every five minutes:

```cron
*/5 * * * * cd /path/to/autopulse/backend && /path/to/uv run python -m autopulse_backend.jobs retention-once >>/var/log/autopulse-retention.log 2>&1
```

## Operational runbooks

- Alert delivery setup and verification: `backend/ALERT_DELIVERY_RUNBOOK.md`
- Release/incident drill gates: `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md` and `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`

## Scope and constraints

Product/architecture source of truth remains `DEVELOPMENT.md`.
