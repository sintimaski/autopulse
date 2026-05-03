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

  The SDK wheel already includes static UI assets under `autopulse/ui/` (refresh with `scripts/bundle_embedded_dashboard_ui.sh` when the Next app changes). No Node/npm is needed at install time.

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

If **either** variable is missing, the sender stays off: middleware still runs, but **no events are enqueued** (minimal overhead on headers/query capture). A **one-time `WARNING`** is emitted on process startup so misconfiguration is obvious without breaking the host app.

## Key runtime controls

- `AUTOPULSE_API_KEY`
- `AUTOPULSE_EMBEDDED_API_KEY` (embedded only): bearer for ingest + DB seed. If unset, the SDK reads **`.env.autopulse`** (`AUTOPULSE_EMBEDDED_API_KEY` line), then the legacy **`.autopulse/embedded-api-key`** line file, then generates **`.env.autopulse`** with ingest + `NEXT_PUBLIC_*` keys (override path with `AUTOPULSE_ENV_AUTOPULSE_FILE`). Legacy-only path override: `AUTOPULSE_EMBEDDED_API_KEY_FILE`.
- `AUTOPULSE_EMBEDDED_STARTUP_INGEST` (embedded only, default on): when truthy, enqueue one synthetic `GET /.well-known/autopulse-onboarding` request after the sender starts so onboarding can advance before real traffic.
- `AUTOPULSE_INGEST_URL` (or `AUTOPULSE_ENDPOINT`)
- `AUTOPULSE_FLUSH_INTERVAL_SECONDS`
- `AUTOPULSE_BATCH_MAX_EVENTS`
- `AUTOPULSE_MAX_QUEUE_SIZE`
- `AUTOPULSE_DEBUG`

`monitor()` also supports explicit kwargs for runtime behavior:
- `capture_headers` (default `True`)
- `capture_query_params` (default `True`)
- `scrub_keys` (additional sensitive keys to redact)
- `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s`

## Security defaults

- Sensitive keys are scrubbed before send.
- Capture is conservative by default.
- Middleware captures error context and re-raises original exceptions.

Canonical behavior and constraints are defined in `DEVELOPMENT.md`.
