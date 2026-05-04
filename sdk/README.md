# AutoPulse SDK (Python)

AutoPulse SDK instruments a FastAPI app and sends request/error events to AutoPulse with safe defaults.

## Install

**Remote ingest only** (no local backend on disk):

```bash
pip install autopulse
```

**Embedded** (`autopulse(app)` — local ingest + API + bundled Next dashboard under `/autopulse/ui/`):

- **Once `autopulse-backend` is on the same package index as `autopulse` (e.g. PyPI):**

  ```bash
  pip install "autopulse[embedded]"
  ```

- **Before that, or from a git checkout:** build both wheels and install in one go (requires **Python ≥ 3.11**):

  ```bash
  ./scripts/build_sdk_release_wheels.sh   # from repo root; writes dist/wheels/*.whl
  pip install dist/wheels/autopulse_backend-*.whl dist/wheels/autopulse-*.whl
  ```

  The SDK wheel includes static UI assets under `autopulse/ui/` (built during `uv build --package autopulse --wheel` from `frontend/`; for local work use `scripts/bundle_embedded_dashboard_ui.sh`). No Node/npm is needed at **install** time.

## Embedded (local dashboard + ingest), one line

```python
from fastapi import FastAPI
from autopulse import autopulse

app = FastAPI()
autopulse(app)
```

`autopulse()` defaults **`environment` to `development`** so request events match common dashboard server-scope filters. Use `autopulse(app, environment="production")` when you need production labels.

## Remote-only integration

```python
from autopulse import monitor

monitor(app)
```

By default, `monitor()` targets a remote AutoPulse project (set `AUTOPULSE_API_KEY` / `AUTOPULSE_INGEST_URL`). It uses bounded in-memory buffering, async background sending, and silent failure behavior so host apps stay healthy if AutoPulse is unavailable.

If **either** variable is missing, the sender stays off: middleware still runs, but **no events are enqueued** (minimal overhead). A **one-time `WARNING`** is emitted on process startup so misconfiguration is obvious without breaking the host app.

## Key runtime controls

- `AUTOPULSE_API_KEY`
- `AUTOPULSE_EMBEDDED_API_KEY` (embedded only): bearer for ingest + DB seed. If unset, the SDK reads **`.env.autopulse`** (`AUTOPULSE_EMBEDDED_API_KEY` line), then the legacy **`.autopulse/embedded-api-key`** line file, then generates **`.env.autopulse`** with ingest + `NEXT_PUBLIC_*` keys (override path with `AUTOPULSE_ENV_AUTOPULSE_FILE`). Legacy-only path override: `AUTOPULSE_EMBEDDED_API_KEY_FILE`.
- `AUTOPULSE_EMBEDDED_STARTUP_INGEST` (embedded only, default on): when truthy, enqueue one synthetic `GET /.well-known/autopulse-onboarding` request after the sender starts so onboarding can advance before real traffic.
- `AUTOPULSE_INGEST_URL` (or `AUTOPULSE_ENDPOINT`)
- `AUTOPULSE_FLUSH_INTERVAL_SECONDS`
- `AUTOPULSE_BATCH_MAX_EVENTS`
- `AUTOPULSE_MAX_QUEUE_SIZE`
- `AUTOPULSE_DEBUG`
- `AUTOPULSE_CAPTURE_HEADERS` — when `true`/`1`/`yes`, capture request headers in events (default **off** for production-safe privacy).
- `AUTOPULSE_CAPTURE_QUERY_PARAMS` — when truthy, capture query parameters (default **off**).

`monitor()` also supports explicit kwargs for runtime behavior:
- `capture_headers` (default follows `AUTOPULSE_CAPTURE_HEADERS`, else **False**)
- `capture_query_params` (default follows `AUTOPULSE_CAPTURE_QUERY_PARAMS`, else **False**)
- `scrub_keys` (additional sensitive keys to redact)
- `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s`

## Security defaults

- Sensitive keys are scrubbed before send.
- **Headers and query strings are not captured unless explicitly enabled** (kwargs or env vars above)—opt in when debugging, not in production, unless you accept the PII risk.
- Middleware captures error context and re-raises original exceptions.

## Troubleshooting (“no events”)

1. Confirm `AUTOPULSE_API_KEY` and `AUTOPULSE_INGEST_URL` are both set for `monitor()` (see startup `WARNING` when remote send is disabled).
2. Enable `AUTOPULSE_DEBUG=1` temporarily to surface queue drops or send failures on stderr.
3. Check dashboard server-scope filters (environment / service) vs the `environment` and `service_name` fields you send from the SDK.
4. Embedded: verify `AUTOPULSE_EMBEDDED_API_KEY` matches the DB-seeded key (see `.env.autopulse`); if `.env.autopulse` could not be written, the SDK logs a warning and uses an **ephemeral** generated key for that process only.
5. Dashboard shows traffic but **requests/errors look empty** while DuckDB tools show rows: you likely opened a **different** DuckDB file than the API. Set `AUTOPULSE_DATA_DIR` or an absolute `AUTOPULSE_DUCKDB_PATH` on the backend and confirm startup logs (`Startup settings [event_store]: … duckdb_path=…`).

Canonical behavior and constraints are defined in `DEVELOPMENT.md`.
