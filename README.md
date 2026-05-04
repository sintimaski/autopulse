# AutoPulse

**Stack:** FastAPI (your app + ingestion API), **Next.js** and **Tailwind** (dashboard UI), **SQLite** (projects, keys, sessions), **DuckDB** (high-volume HTTP events).

The **Python SDK** (`autopulse`) instruments FastAPI; the **backend** (`autopulse_backend`) serves ingest, dashboard JSON, auth, and jobs. The SDK uses **remote ingest**: your app sends events to a separate AutoPulse API process.

---

## Install & run

```bash
pip install autopulse
```

```python
from fastapi import FastAPI
from autopulse import autopulse

app = FastAPI()
autopulse(app)
```

### 1. Remote ingest — local backend

Your app posts events to an AutoPulse API running on your machine (e.g. monorepo `./scripts/run_synthetic_stack.sh` or `uv run python -m autopulse_backend.main`).

```bash
export AUTOPULSE_INGEST_URL="http://127.0.0.1:8000/ingest"
export AUTOPULSE_API_KEY="<project API key>"
```

Use the ingest URL your backend actually exposes (host, port, and path prefix must match).

### 2. Remote ingest — hosted backend

```bash
export AUTOPULSE_INGEST_URL="https://<host>/<prefix>/ingest"
export AUTOPULSE_API_KEY="<project API key>"
```

Operations: [docs/ops/PRODUCTION_DEPLOYMENT.md](./docs/ops/PRODUCTION_DEPLOYMENT.md).

---

## Custom dashboard widgets

Pass `dashboard_widgets=(...)` to `autopulse` with `CardWidget`, `LineChartWidget`, `BarChartWidget`, `DonutChartWidget`, `HistogramWidget`, `ScatterPlotWidget`, `StackedAreaWidget` from `autopulse`. Types: `card`, `line`, `bar`, `donut`, `histogram`, `scatter`, `stacked_area`.

```python
from datetime import UTC, datetime, timedelta
from fastapi import FastAPI
from autopulse import CardWidget, LineChartWidget, autopulse

app = FastAPI()
autopulse(
    app,
    dashboard_widgets=[
        CardWidget(widget_id="n", title="Count", value=42.0, unit="n", order=10),
        LineChartWidget(
            widget_id="t",
            title="Series",
            points=[(datetime.now(tz=UTC) - timedelta(minutes=1), 1.0), (datetime.now(tz=UTC), 2.0)],
            order=20,
        ),
    ],
)
```

API details: `sdk/src/autopulse/widgets.py`. Full fixture example: `sdk/src/autopulse/fixtures/synthetic_test_app.py` (`_build_demo_dashboard_widgets`).

**UI:** widgets page `/autopulse/ui/widgets-showcase` (live scope + mock preview; legacy `/widgets-showroom` redirects here; paths follow the static export `basePath`; adjust if you host the UI elsewhere).

---

## Components

| Piece | Location | Role |
|-------|----------|------|
| SDK | `sdk/` | Middleware, buffered sender (remote ingest) |
| Backend | `backend/` | Ingest, dashboard JSON API, auth, jobs |
| Relational DB | `DATABASE_URL` | Projects, keys, sessions |
| Events | `AUTOPULSE_DUCKDB_PATH` | HTTP events (DuckDB by default in dev) |
| Dashboard | `frontend/` → `npm run build` → `frontend/out/` | Overview, requests, diagnosis |

---

## How to run things

| Goal | Command / notes |
|------|-----------------|
| Full repo demo | `uv sync --group dev`, `npm --prefix frontend install`, `cp backend/.env.example backend/.env`, `./scripts/run_synthetic_stack.sh` (backend :8000 + synthetic app :8001) |
| Backend only | `uv run python -m autopulse_backend.main` + `backend/.env` or `AUTOPULSE_BACKEND_DOTENV` |
| Split API + Next dev | `./scripts/run_remote_stack.sh` for hints; backend + `npm --prefix frontend run dev` |
| Load generator | `uv run python -m autopulse.fixtures.synthetic_load --base-url http://127.0.0.1:8001 --duration-seconds 120 --rps 8 --role-mode mixed` (with `run_synthetic_stack.sh`; use your instrumented app URL otherwise) |

**Frontend:** `AUTOPULSE_FRONTEND_MODE=sidecar` — Next dev; set `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` to the API origin (e.g. `http://127.0.0.1:8000`, no `/autopulse` path — dashboard JSON is at `/dashboard/...`). `static` — build export; same-origin UI can leave this unset so the browser calls `/dashboard/...` on the same host.

**Synthetic stack env (common):** `AUTOPULSE_FRONTEND_MODE`, `AUTOPULSE_MOUNT_PREFIX`, `AUTOPULSE_SIDECAR_API_BASE_URL`, `AUTOPULSE_DATA_DIR`, `AUTOPULSE_API_KEY` — see `sdk/src/autopulse/fixtures/README.md`.

---

## `autopulse(app, **kwargs)` (recommended)

Remote defaults: `mode="remote"`. Ingest from `ingest_url` / `AUTOPULSE_INGEST_URL` / `AUTOPULSE_ENDPOINT` and `api_key` / `AUTOPULSE_API_KEY`.

`monitor(app, **kwargs)` remains supported for backward compatibility, but new integrations should prefer `autopulse(app, **kwargs)` for a one-line default setup.

| Parameter | Notes |
|-----------|--------|
| `mode` | `remote` (only supported mode; `embedded` is ignored with a warning) |
| `api_key`, `ingest_url` | Override env |
| `service_name`, `environment` | Event labels |
| `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s` | Sender / batching |
| `debug` | `AUTOPULSE_DEBUG` |
| `mount_prefix` | Align with submounted AutoPulse |
| `capture_headers`, `capture_query_params`, `scrub_keys` | Privacy / capture |
| `request_sample_rate`, `ignore_path_prefixes` | Volume control (sample high-volume requests, ignore health/noise routes) |
| `dashboard_widgets` | Custom charts |
| `capture_infrastructure_metrics`, `infrastructure_probe_interval_ms` | Host metrics |
| `startup_ingest_ping`, `http_client`, `owns_http_client` | See SDK source |

---

## Environment reference

**SDK:** `AUTOPULSE_API_KEY`, `AUTOPULSE_INGEST_URL` / `AUTOPULSE_ENDPOINT`, `AUTOPULSE_MAX_QUEUE_SIZE`, `AUTOPULSE_BATCH_MAX_EVENTS`, `AUTOPULSE_FLUSH_INTERVAL_SECONDS`, `AUTOPULSE_DEBUG`, `AUTOPULSE_CAPTURE_HEADERS`, `AUTOPULSE_CAPTURE_QUERY_PARAMS`, `AUTOPULSE_REQUEST_SAMPLE_RATE` (0.0-1.0), `AUTOPULSE_IGNORE_PATH_PREFIXES` (comma-separated route prefixes; default `/health,/ready`), `AUTOPULSE_INFRA_PROBE_INTERVAL_MS`.

**Backend:** `DATABASE_URL`, `AUTOPULSE_EVENT_STORE`, `AUTOPULSE_DUCKDB_PATH`, `AUTOPULSE_DATA_DIR`, `AUTOPULSE_BACKEND_DOTENV`, `CORS_ALLOW_ORIGINS`, `AUTOPULSE_SQLITE_MAX_DB_FILE_MB` (deprecated alias `AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB`), `AUTOPULSE_ENV_AUTOPULSE_FILE`, plus `DASHBOARD_AUTH_*`, `ALERT_*`, `INGEST_*`, `JOBS_*` — full list in [backend/README.md](./backend/README.md) and `core/config.py`.

**Frontend:** `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL`, `NEXT_PUBLIC_AUTOPULSE_API_KEY`, `NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN`, `NEXT_PUBLIC_AUTOPULSE_FRONTEND_MODE`, `AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS`, `NEXT_PUBLIC_AUTOPULSE_ADVANCED_QUERY_UI`, `NEXT_PUBLIC_AUTOPULSE_DASHBOARD_REFRESH_INTERVAL_SECONDS`, `NEXT_PUBLIC_AUTOPULSE_DASHBOARD_REWRITE_PHASED`. Copy [frontend/.env.example](./frontend/.env.example) → `frontend/.env.local`.

---

## Repo layout

| Path | Contents |
|------|----------|
| `sdk/` | `autopulse` |
| `backend/` | `autopulse_backend` |
| `frontend/` | Dashboard |
| `scripts/` | Stack runners, wheels |
| `agents/`, `docs/` | Playbooks, ops, governance |

---

## Tooling & docs

Python **3.11+**, [uv](https://docs.astral.sh/uv/), Node for `frontend/`. Hooks: `uv run pre-commit install`.

| Topic | Link |
|-------|------|
| Product & MVP | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| Agents | [AGENTS.md](./AGENTS.md) |
| Backend | [backend/README.md](./backend/README.md) |
| Dev process | [docs/DEVELOPMENT_PROCESS.md](./docs/DEVELOPMENT_PROCESS.md) |
| Production | [docs/ops/PRODUCTION_DEPLOYMENT.md](./docs/ops/PRODUCTION_DEPLOYMENT.md) |
| Multi-instance | [docs/ops/DEPLOYMENT_MULTI_INSTANCE.md](./docs/ops/DEPLOYMENT_MULTI_INSTANCE.md) |
| Backup / restore | [docs/ops/BACKUP_RESTORE.md](./docs/ops/BACKUP_RESTORE.md) |
