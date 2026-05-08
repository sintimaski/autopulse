# AutoPulse Backend

FastAPI backend for ingest, dashboard APIs, auth/session flows, alerts, retention jobs, and realtime updates.

Python **import name** remains **`autopulse_backend`**. The **distribution / PyPI project name** is **`autopulse-api`** (API + pre-built dashboard static export bundled in the wheel). The PyPI name **`autopulse`** is already used by an unrelated package, so this project publishes as **`autopulse-api`**. If you used **`autopulse-backend`** or **`autopulse`** in Git URLs earlier, switch to **`autopulse-api`** (same code paths).

## What lives here

- Ingest API: `POST /ingest` with API-key authentication.
- Dashboard API: overview, requests, error groups, diagnosis, alerts, settings, log query, organizations.
- Dashboard auth: magic-link sign-in, cookie sessions, tenant bootstrap endpoint.
- Background jobs: alert evaluation and retention cleanup.
- Internal ops endpoints: health/ready and service metrics.

## Install outside the monorepo

**One line (PyPI, after trusted publishing is enabled):**

```bash
pip install autopulse-api
```

```bash
uv add autopulse-api
```

**One line (Git — always works; pin `main` to a tag or SHA in production):**

```bash
uv add "autopulse-api @ git+https://github.com/sintimaski/autopulse.git@main#subdirectory=backend"
```

```bash
pip install "autopulse-api @ git+https://github.com/sintimaski/autopulse.git@main#subdirectory=backend"
```

**API + Fast instrumented app in one line:** use the SDK extra (see [sdk/README.md](../sdk/README.md)):

```bash
pip install "autopulse-sdk[stack]"
```

If Python **3.14** fails to resolve wheels, try **3.12 or 3.13**.

### Wheel build (bundled dashboard)

The **`autopulse-api`** sdist/wheel ships the Next static export under **`autopulse_backend/dashboard_static/`** (mounted at **`/autopulse/ui/`** when **`AUTOPULSE_FRONTEND_STATIC_DIR`** is unset and **`index.html`** exists). Build **`frontend/out`** first (see **`scripts/run_synthetic_stack.sh`** for **`NEXT_PUBLIC_*`** defaults):

```bash
./backend/scripts/package_wheel.sh
```

## Run locally

From repository root:

```bash
uv sync --group dev
# Loads backend/.env so retention/cap settings are actually applied.
uv run uvicorn autopulse_backend.main:app --env-file backend/.env --log-level info
```

Backend defaults to `http://localhost:8000`.

## Key environment variables

- `DATABASE_URL` (default SQLite file: `.autopulse/autopulse.db` under the repo root—same directory tree as DuckDB; see `normalize_database_url` in `core/config.py`)
- `AUTOPULSE_EVENT_STORE` (`duckdb` default; set `sqlite` to force legacy SQL event reads)
- `AUTOPULSE_DUCKDB_PATH` (DuckDB event store file; relative values anchor under `AUTOPULSE_DATA_DIR` / `AUTOPULSE_PROJECT_ROOT`, else monorepo root—see `normalize_event_store_duckdb_path` / `resolve_autopulse_data_root` in `core/config.py`; use absolute paths in production if you prefer)
- `AUTOPULSE_DATA_DIR` / `AUTOPULSE_PROJECT_ROOT` (optional; pins the root for relative DuckDB paths and keeps ingest/dashboard/CLI on one file regardless of shell cwd)
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
- `AUTOPULSE_ENV_AUTOPULSE_FILE` (optional path to the `.env.autopulse` bundle for local static UI builds; default `./.env.autopulse` at process cwd)
- `AUTOPULSE_SQLITE_MAX_DB_FILE_MB` (max SQLite log-store file size in MB; applies to DuckDB or SQLite when capped. For SQLite it includes main + `-wal` + `-shm`; deprecated alias `AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB`; default **512** on dev default SQLite filenames when unset)
- `AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS` / `AUTOPULSE_RETENTION_PRESSURE_MIN_INTERVAL_SECONDS` (SQLite pressure poll; see `core/config.py`)

Parquet **object storage** with `AUTOPULSE_PARQUET_OBJECT_STORAGE_URI=s3://...` needs **`boto3`**. Install the extra from this directory (`uv pip install -e ".[parquet-s3]"`) or add `boto3` to your environment. `file://` URIs do not use `boto3`.

See `backend/src/autopulse_backend/core/config.py` and `backend/.env.example` for the complete list and defaults.

**Production:** startup applies `validate_deployment_settings` for `AUTOPULSE_ENV=production`. Follow `docs/ops/PRODUCTION_DEPLOYMENT.md` for enforced HTTPS ingest, internal metrics token, CORS, dashboard session/magic-link TTL, OIDC/magic-link URL schemes, and related constraints. Automated checks: `backend/tests/test_deployment_settings.py`.

## Testing (backend)

- Unit-style deployment guardrails: `uv run pytest backend/tests/test_deployment_settings.py`
- Integration tests under `backend/tests/` that need a real DB URL skip unless `BACKEND_TEST_DATABASE_URL` is set (see `backend/tests/conftest.py`). Example: `export BACKEND_TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/ap-test.db` then run targeted files such as `backend/tests/test_dashboard_auth.py`.

## Retention scheduling (FastAPI-optional)

The portable unit of work is **one retention pass** (SQLite caps, time windows, aggregates trim):

| How | Command / API |
|-----|-----------------|
| **CLI (any OS, no web server)** | `cd backend && uv run python -m autopulse_backend.jobs retention-once` |
| **Sync Python (cron, Django command, systemd `ExecStart`)** | `from autopulse_backend.jobs import run_retention_sync` then `run_retention_sync()` after setting `DATABASE_URL` in the environment |
| **In-process (FastAPI)** | Lifespan starts the scheduler or retention-only loop; optional SQLite pressure poll |

For **Linux production** or **Django** (no FastAPI event loop), prefer **cron** or **systemd timers** calling the CLI or `run_retention_sync()` on the interval you want, and set `JOBS_ENABLE_SCHEDULER=false` on the API so you do not double-run retention in-process and from cron.

## Event store migration helpers

- Backfill SQL `events` rows into the DuckDB event store:

```bash
cd backend
uv run python scripts/backfill_events_to_duckdb.py --batch-size 1000
```

Example cron every five minutes:

```cron
*/5 * * * * cd /path/to/autopulse/backend && /path/to/uv run python -m autopulse_backend.jobs retention-once >>/var/log/autopulse-retention.log 2>&1
```

## Operational runbooks

- Alert delivery setup and verification: `backend/ALERT_DELIVERY_RUNBOOK.md`
- Release/incident drill gates: `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md` and `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`

## Scope and constraints

Product/architecture source of truth remains `DEVELOPMENT.md`.
