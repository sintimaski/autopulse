# AutoPulse

**FastAPI observability in one vertical slice:** Python SDK, FastAPI **backend** (ingest + dashboard API + auth + jobs), **frontend** (Next.js), and **databases** (relational metadata + high-volume event store)—wired so you can run a **single process** with everything mounted, or split pieces for production.

Canonical product scope: **[DEVELOPMENT.md](./DEVELOPMENT.md)** · Contributor entry: **[AGENTS.md](./AGENTS.md)**

---

## What runs where

| Layer | Package / path | Role |
|--------|----------------|------|
| **SDK** | `autopulse` (`sdk/`) | Middleware, buffered sender, optional embedded mount |
| **Backend** | `autopulse_backend` (`backend/`) | `POST /ingest`, dashboard JSON API, magic-link auth, alerts & retention jobs |
| **Relational DB** | SQLite by default (`DATABASE_URL`) | Projects, API keys, sessions, aggregates metadata |
| **Event store** | DuckDB file (`AUTOPULSE_DUCKDB_PATH`) | Raw HTTP events at scale (default in dev stacks) |
| **Dashboard UI** | `frontend/` → static export in `sdk/src/autopulse/ui/` (built locally / in wheel; not tracked) | Overview, requests, diagnosis, alerts |

---

## Operating modes (pick one path)

| Mode | When to use | Moving parts |
|------|-------------|--------------|
| **Remote ingest** | Production or hosted AutoPulse; your app only needs the SDK | User app → HTTPS → backend + DBs you operate |
| **Embedded + static UI** | One FastAPI app ships observability beside its routes | `monitor(..., mode="embedded")` mounts backend under a prefix; dashboard is **static files** (bundled export or `frontend_static_dir`) |
| **Embedded + sidecar UI** | Same as embedded, but you want **Next dev** (HMR) on port 3000 | API on :8000, `npm run dev` in `frontend/` started by script or `frontend_sidecar_command` |
| **Split stack (local)** | Iterate on backend or frontend alone | `autopulse_backend.main` + `npm --prefix frontend run dev` with `NEXT_PUBLIC_*` pointing at the API |
| **Synthetic fixture stack** | CI / demos / “does the whole repo work?” | `./scripts/run_synthetic_stack.sh` — DuckDB + optional Next sidecar (default) or static build |

**Frontend delivery**

- **`AUTOPULSE_FRONTEND_MODE=sidecar`** (default in `run_synthetic_stack.sh`): Next dev server; set `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` to the full API base (script sets `http://127.0.0.1:8000/autopulse` unless you override `AUTOPULSE_SIDECAR_API_BASE_URL`).
- **`AUTOPULSE_FRONTEND_MODE=static`**: runs `npm --prefix frontend run build`; serve UI from the API host under `/autopulse/ui/` (same-origin; use path-only `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL=/autopulse`).

**Embedded ingest transport** (`embedded_ingest_transport` or `AUTOPULSE_EMBEDDED_INGEST_TRANSPORT`):

- **`http`** (default): loopback uvicorn + HTTP ingest (matches production behavior).
- **`asgi`**: in-process ASGI transport (smaller surface; different latency characteristics).

---

## User flows (cheat sheet)

1. **Production / hosted** — Install `pip install autopulse`, set `AUTOPULSE_INGEST_URL` + `AUTOPULSE_API_KEY`, call `monitor(app)`. Operate backend + DBs per **[docs/ops/PRODUCTION_DEPLOYMENT.md](./docs/ops/PRODUCTION_DEPLOYMENT.md)**.
2. **Embedded in your FastAPI app** — `pip install "autopulse[embedded]"` (needs **`autopulse-backend`** on the index or install both wheels from `./scripts/build_sdk_release_wheels.sh`), then `monitor(app, mode="embedded", ...)`. First boot can create repo-root **`.env.autopulse`** with keys for UI builds.
3. **Monorepo dev (recommended)** — `uv sync --group dev`, `npm --prefix frontend install`, `cp backend/.env.example backend/.env`, then `./scripts/run_synthetic_stack.sh`.
4. **Backend-only terminal** — `uv run python -m autopulse_backend.main` (load `backend/.env` via your process manager or `AUTOPULSE_BACKEND_DOTENV`).
5. **Split local without fixture** — `./scripts/run_remote_stack.sh` prints env hints; start backend + `npm --prefix frontend run dev` in two shells.
6. **Generate traffic** — e.g. `uv run python -m autopulse.fixtures.synthetic_load --base-url http://localhost:8000 --duration-seconds 120 --rps 8 --role-mode mixed`.

Embedded HTTP surface (typical mount prefix **`/autopulse`**): dashboard and API live under `http://<host>:<port>/autopulse/…`.

### `run_synthetic_stack.sh` — extra env

| Variable | Default / notes |
|----------|-----------------|
| `AUTOPULSE_FRONTEND_MODE` | `sidecar` (set `static` for export-only UI on :8000) |
| `AUTOPULSE_MOUNT_PREFIX` | `/autopulse` (fixture app; see `sdk/src/autopulse/fixtures/README.md`) |
| `AUTOPULSE_SIDECAR_API_BASE_URL` | When set to origin-only, script appends mount prefix for Next |
| `AUTOPULSE_DATA_DIR` | Repo root; pins DuckDB path for consistent reads |

---

## `monitor(app, **kwargs)` — parameters

All arguments are optional unless you use remote ingest without env vars (then set **`ingest_url`** + **`api_key`**).

| Parameter | Meaning |
|-----------|---------|
| `mode` | `"remote"` (default) or `"embedded"` |
| `api_key` | Project API key (else `AUTOPULSE_API_KEY`) |
| `ingest_url` | Ingest base URL (else `AUTOPULSE_INGEST_URL` or `AUTOPULSE_ENDPOINT`) |
| `service_name` | Label stored on events (default `api`) |
| `environment` | Label stored on events (default `production`) |
| `queue_maxsize` | Bounded in-memory queue before drops (else `AUTOPULSE_MAX_QUEUE_SIZE`, default `1000`) |
| `batch_size` | Events per POST (else `AUTOPULSE_BATCH_MAX_EVENTS`, default `50`) |
| `flush_interval_s` | Max time before flush (else `AUTOPULSE_FLUSH_INTERVAL_SECONDS`, default `2.0`) |
| `max_retries` | Send retries (default `3`) |
| `retry_backoff_s` | Initial backoff seconds (default `0.1`) |
| `debug` | Verbose stderr logs (else truthy `AUTOPULSE_DEBUG`) |
| `mount_prefix` | e.g. `"/autopulse"` — aligns paths when your app hosts AutoPulse under a prefix |
| `capture_headers` | Record headers (else `AUTOPULSE_CAPTURE_HEADERS`, default off) |
| `capture_query_params` | Record query strings (else `AUTOPULSE_CAPTURE_QUERY_PARAMS`, default off) |
| `scrub_keys` | Extra header/param names to redact (merged with built-in list) |
| `dashboard_widgets` | Sequence of `BaseDashboardWidget` for embedded dashboard |
| `capture_infrastructure_metrics` | Host probes (default `True`; `False` disables sampler) |
| `infrastructure_probe_interval_ms` | Probe cadence in ms (else `AUTOPULSE_INFRA_PROBE_INTERVAL_MS`; remote default `0`) |
| `embedded_startup_ingest_ping` | One-shot onboarding ping when sender starts (embedded path also respects `AUTOPULSE_EMBEDDED_STARTUP_INGEST`) |
| `http_client` | Inject `httpx.AsyncClient` |
| `owns_http_client` | If omitted with a custom `http_client`, the SDK assumes **you** own the client (`False`); pass explicitly if you want the SDK to close it |

**Embedded-only** (ignored when `mode != "embedded"`):

| Parameter | Meaning |
|-----------|---------|
| `database_url` | SQLAlchemy URL for metadata DB (default embedded SQLite under `./.autopulse/`) |
| `embedded_project_name` | Seed project name |
| `frontend_mode` | `"static"` or `"sidecar"` (else `AUTOPULSE_FRONTEND_MODE`; code default for embedded without env is **`static`**) |
| `frontend_static_dir` | Override path to static export directory |
| `embedded_ingest_transport` | `"http"` or `"asgi"` |
| `frontend_sidecar_command` / `frontend_sidecar_cwd` | Custom sidecar command / cwd (else `AUTOPULSE_FRONTEND_SIDECAR_COMMAND` / `AUTOPULSE_FRONTEND_DIR`) |

---

## SDK environment variables

| Variable | Purpose |
|----------|---------|
| `AUTOPULSE_API_KEY` | Bearer for ingest |
| `AUTOPULSE_INGEST_URL` / `AUTOPULSE_ENDPOINT` | Ingest URL |
| `AUTOPULSE_MAX_QUEUE_SIZE` | Queue bound |
| `AUTOPULSE_BATCH_MAX_EVENTS` | Batch size |
| `AUTOPULSE_FLUSH_INTERVAL_SECONDS` | Flush interval |
| `AUTOPULSE_DEBUG` | Enable SDK debug logging |
| `AUTOPULSE_CAPTURE_HEADERS` | Capture headers |
| `AUTOPULSE_CAPTURE_QUERY_PARAMS` | Capture query params |
| `AUTOPULSE_INFRA_PROBE_INTERVAL_MS` | Infrastructure probe interval |

---

## Backend environment (essentials)

Set via `backend/.env`, process env, or `AUTOPULSE_BACKEND_DOTENV` (absolute path to a dotenv file).

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL (default SQLite under `.autopulse/`) |
| `AUTOPULSE_EVENT_STORE` | `duckdb` vs legacy `sqlite` reads |
| `AUTOPULSE_DUCKDB_PATH` | DuckDB file; **relative paths resolve against `AUTOPULSE_DATA_DIR` / repo root—not shell cwd** |
| `AUTOPULSE_DATA_DIR` / `AUTOPULSE_PROJECT_ROOT` | Anchor for relative DB paths |
| `AUTOPULSE_BACKEND_DOTENV` | Optional absolute path to backend dotenv |
| `CORS_ALLOW_ORIGINS` | Browser origins for credentialed API calls |
| `AUTOPULSE_EMBEDDED_API_KEY` | Bearer shared with embedded UI ingest |
| `AUTOPULSE_ENV_AUTOPULSE_FILE` | Path to `.env.autopulse` bundle (default `./.env.autopulse`) |
| `AUTOPULSE_EMBEDDED_STARTUP_INGEST` | `0` disables startup onboarding ingest |
| `AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB` | Cap for embedded store growth |
| `AUTOPULSE_RUNTIME_EMBEDDED` | Treated as embedded deployment (HTTPS defaults, etc.) |
| `DASHBOARD_AUTH_*` / `ALERT_*` / `INGEST_*` / `JOBS_*` | Auth, alerts, ingest limits, scheduler — see **`backend/README.md`** and **`backend/src/autopulse_backend/core/config.py`** for the full matrix and defaults |

---

## Frontend (`NEXT_PUBLIC_*`)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` | API prefix or full origin (`/autopulse` for same-origin static UI; full URL for sidecar / remote) |
| `NEXT_PUBLIC_AUTOPULSE_API_KEY` | Browser-side bearer (embedded dev key; treat like a secret in real deployments) |
| `NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN` | FastAPI origin when API base is path-only in **sidecar** dev |
| `NEXT_PUBLIC_AUTOPULSE_FRONTEND_MODE` | Set `sidecar` when running Next dev against a remote API host |
| `AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS` | Comma-separated hostnames for Next 16 HMR from LAN IPs |
| `NEXT_PUBLIC_AUTOPULSE_ADVANCED_QUERY_UI` | `1` enables advanced SQL toolbar (internal diagnostics) |
| `NEXT_PUBLIC_AUTOPULSE_DASHBOARD_REFRESH_INTERVAL_SECONDS` | Polling interval |
| `NEXT_PUBLIC_AUTOPULSE_DASHBOARD_REWRITE_PHASED` | `0` disables phased dashboard experiment |

Copy **`frontend/.env.example`** to `frontend/.env.local` for local Next.

---

## Repo layout

| Path | Contents |
|------|----------|
| `sdk/` | `autopulse` package |
| `backend/` | `autopulse_backend` package |
| `frontend/` | Next.js dashboard |
| `scripts/` | `run_synthetic_stack.sh`, `run_remote_stack.sh`, wheel build, UI bundle |
| `agents/` | Implementation / review playbooks |
| `docs/` | Ops runbooks, Cursor notes, governance |

---

## Install & minimal code

```bash
pip install autopulse                 # remote ingest only
pip install "autopulse[embedded]"     # needs autopulse-backend on your index
```

```python
from fastapi import FastAPI
from autopulse import monitor

app = FastAPI()
monitor(app)  # remote: set AUTOPULSE_INGEST_URL + AUTOPULSE_API_KEY
# monitor(app, mode="embedded")      # full stack in-process (requires autopulse-backend)
```

---

## Tooling

Python **3.11+**, **[uv](https://docs.astral.sh/uv/)**, Node.js for `frontend/`. Install hooks: `uv run pre-commit install`. CI covers Python + frontend checks.

---

## Documentation index

| Topic | Link |
|--------|------|
| Product & MVP | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| Agent workflow | [AGENTS.md](./AGENTS.md) |
| Backend details | [backend/README.md](./backend/README.md) |
| Development process | [docs/DEVELOPMENT_PROCESS.md](./docs/DEVELOPMENT_PROCESS.md) |
| Production rollout | [docs/ops/PRODUCTION_DEPLOYMENT.md](./docs/ops/PRODUCTION_DEPLOYMENT.md) |
| Multi-instance | [docs/ops/DEPLOYMENT_MULTI_INSTANCE.md](./docs/ops/DEPLOYMENT_MULTI_INSTANCE.md) |
| Backup / restore | [docs/ops/BACKUP_RESTORE.md](./docs/ops/BACKUP_RESTORE.md) |

---

AutoPulse targets **small FastAPI teams** who want signal fast—not a full replacement for every enterprise APM surface.
