# Lumonox SDK (Python)

Lumonox SDK instruments **FastAPI** and **Django** apps and sends request/error events to Lumonox with safe defaults. The default install ships the FastAPI adapter; the `[django]` extra adds the Django ASGI adapter.

## Install

| Goal | PyPI one-liner | Import / process |
|------|-----------------|------------------|
| **API + bundled dashboard UI** (ingest, dashboard, static export under `/lumonox/ui/`) | `pip install lumonox` | `from lumonox import mount_on_app` (or `lumonox_backend` / `uvicorn lumonox_backend.main:app`) |
| **Instrument your FastAPI app** (send-only SDK) | `pip install lumonox-sdk` | `from lumonox import lumonox` |
| **Instrument your Django app** (async ASGI middleware) | `pip install "lumonox-sdk[django]"` | `from lumonox.django import monitor, wrap_asgi` |
| **API + UI + SDK in one environment** | `pip install "lumonox-sdk[stack]"` | `from lumonox import lumonox, mount_on_app` |

`uv add` works the same (`uv add lumonox`, `uv add "lumonox-sdk[stack]"`, …).

### Compatibility

`lumonox-sdk` is published as a pure-Python `py3-none-any` wheel. Minimum supported versions:

| Component | Floor | Notes |
|-----------|-------|-------|
| **Python** | `>=3.10` | Tested on 3.10 – 3.13 (linux/amd64 + linux/arm64, glibc-slim and musl-alpine). |
| **fastapi** | `>=0.100.0` | The middleware only needs Starlette's `BaseHTTPMiddleware` and the request/response shapes. No upper cap. |
| **httpx** | `>=0.24.0` | Uses `AsyncClient`, `HTTPStatusError`, and the `Response` headers/status_code surface. No upper cap. |
| **psutil** | `>=5.9.0` | Required for the host/process/disk/network metrics shown on the dashboard infrastructure cards. No upper cap. |

Floors are intentionally generous so a host app that pins an older fastapi / httpx / psutil line resolves cleanly. See `docs/plans/sdk-install-ease.md` for the audit that picked these floors.

**From a git checkout** (offline wheels from repo root):

```bash
./scripts/build_sdk_release_wheels.sh   # writes dist/wheels/*.whl
pip install dist/wheels/lumonox-*.whl dist/wheels/lumonox_sdk-*.whl
```

## Publish to PyPI

Artifacts are standard **wheel + sdist** from the workspace root (`hatchling` via `uv build`):

```bash
uv build --package lumonox-sdk -o dist/pypi-sdk
python -m pip install twine   # once
twine check dist/pypi-sdk/*
twine upload dist/pypi-sdk/*
```

**Recommended:** use [trusted publishing](https://docs.pypi.org/trusted-publishers/) from GitHub Actions instead of storing a long-lived PyPI token in CI secrets:

- **SDK:** `.github/workflows/publish-lumonox-sdk-pypi.yml` → project **`lumonox-sdk`**
- **API + bundled UI:** `.github/workflows/publish-lumonox-pypi.yml` → project **`lumonox`**

**On `main`:** the SDK workflow runs when `sdk/pyproject.toml`, `sdk/src/**`, `sdk/README.md`, or `sdk/LICENSE` change. The **`lumonox`** publish workflow runs when `backend/pyproject.toml`, `backend/src/**`, or `frontend/**` change. Both upload **only when** the corresponding `[project] version` is **not already** on PyPI.

**`lumonox-sdk[stack]` on PyPI:** publish **`lumonox`** first (or same release train) so the extra can resolve **`lumonox>=0.2.9`** (see `sdk/pyproject.toml` **`[project.optional-dependencies]`**).

**One-time on PyPI:** create projects **`lumonox-sdk`** and **`lumonox`**, add trusted publishers for each workflow, then merge version bumps or run workflows manually.

## Integration

### FastAPI

```python
from fastapi import FastAPI
from lumonox import lumonox, monitor

app = FastAPI()
lumonox(app)  # recommended default
# monitor(app)  # backwards-compatible alias for existing integrations
```

`lumonox()` defaults **`environment` to `development`** so request events match common dashboard server-scope filters. Use `lumonox(app, environment="production")` when you need production labels.

### Django (async / ASGI)

```python
# settings.py
MIDDLEWARE = [
    "lumonox.django.middleware.LumonoxMiddleware",
    # ... your other middleware ...
]

# asgi.py
from django.core.asgi import get_asgi_application
from lumonox.django import monitor, wrap_asgi

monitor(
    api_key="...",
    ingest_url="https://your-lumonox/ingest",
    service_name="my-django-app",
    environment="production",
)
application = wrap_asgi(get_asgi_application())
```

``wrap_asgi`` handles the ASGI lifespan protocol so the SDK dispatcher starts/stops with your server. The same ``LUMONOX_*`` env vars apply (``LUMONOX_API_KEY``, ``LUMONOX_INGEST_URL``, ``LUMONOX_REQUEST_SAMPLE_RATE``, …). The adapter is async-only; classic synchronous WSGI Django is out of scope for v1. See ``sdk/docs/adapters.md`` for the adapter contract.

By default, `lumonox()` (and `monitor()` for existing integrations) target a remote Lumonox project (set `LUMONOX_API_KEY` / `LUMONOX_INGEST_URL`). It uses bounded in-memory buffering, async background sending, and silent failure behavior so host apps stay healthy if Lumonox is unavailable.

**`.env` auto-discovery.** To keep config a one-line affair, `lumonox()` / `monitor()` look for a `.env` file next to your app (current working directory, then a few parent directories) and load any **`LUMONOX_*`** keys from it before reading the environment. Only `LUMONOX_*` keys are touched, and **real environment variables always win** (the `.env` only fills in what is unset) — so a `.env` for local dev and shell exports in production coexist cleanly. Opt out with `lumonox(app, load_dotenv=False)`, or point at a specific file with `lumonox(app, dotenv_path="…/.env")`. So the minimal pip-installed setup is:

```dotenv
# .env  (next to your app)
LUMONOX_API_KEY=ap_...
LUMONOX_INGEST_URL=https://your-lumonox/ingest
```

```python
from lumonox import lumonox
lumonox(app)   # picks up the .env above — no shell exports needed
```

If **either** variable is missing, the sender stays off: middleware still runs, but **no events are enqueued** (minimal overhead). A **one-time `WARNING`** is emitted on process startup so misconfiguration is obvious without breaking the host app.

## Key runtime controls

- `LUMONOX_API_KEY`
- `LUMONOX_INGEST_URL` (or `LUMONOX_ENDPOINT`)
- `LUMONOX_FLUSH_INTERVAL_SECONDS`
- `LUMONOX_BATCH_MAX_EVENTS`
- `LUMONOX_MAX_QUEUE_SIZE`
- `LUMONOX_DEBUG`
- `LUMONOX_REQUEST_SAMPLE_RATE` (`0.0`-`1.0`; default `1.0`)
- `LUMONOX_IGNORE_PATH_PREFIXES` (comma-separated, default `/health,/ready`)
- `LUMONOX_CAPTURE_HEADERS` — when `true`/`1`/`yes`, capture request headers in events (default **off** for production-safe privacy).
- `LUMONOX_CAPTURE_QUERY_PARAMS` — when truthy, capture query parameters (default **off**).
- `LUMONOX_INGEST_MAX_BATCH_BYTES` — max UTF-8 JSON size per ingest POST before gzip (default `786432`, sized under the API default `INGEST_MAX_REQUEST_BYTES` of 1 MiB). Oversized logical batches are split automatically.
- `LUMONOX_MAX_CONCURRENT_SENDS` — max parallel ingest POSTs from this process (default `1`).
- `LUMONOX_CIRCUIT_FAILURE_THRESHOLD` — consecutive **terminal** ingest failures (after retries) before the SDK **opens** a cooldown and **fast-fails** further POSTs for `LUMONOX_CIRCUIT_OPEN_SECONDS` (default **`0`** = disabled). Use a small positive value in production when the backend may be unavailable for long stretches. While open, the sender **does not** start new HTTP requests for those batches (no `Idempotency-Key` is consumed server-side for skipped work); each real POST still sends a fresh key.
- `LUMONOX_CIRCUIT_OPEN_SECONDS` — cooldown length after the threshold is hit (default `30`; minimum enforced `0.5`).
- `LUMONOX_RELEASE` — optional short release label (for example `v1.4.2` or a deploy id), trimmed and capped; attached to captured HTTP events, the startup onboarding ping, and infrastructure probe events when set.
- `LUMONOX_GIT_SHA` — optional git commit id (trimmed, capped); stored with events when set so the dashboard can show **release markers** on the overview when the backend aggregates them.

`lumonox()` and `monitor()` support explicit kwargs for runtime behavior:

- `capture_headers` (default follows `LUMONOX_CAPTURE_HEADERS`, else **False**)
- `capture_query_params` (default follows `LUMONOX_CAPTURE_QUERY_PARAMS`, else **False**)
- `request_sample_rate` (float `0.0`-`1.0`, keeps 5xx/error capture unsampled)
- `ignore_path_prefixes` (tuple/list of path prefixes to skip, e.g. `("/health", "/ready")`)
- `scrub_keys` (additional sensitive keys to redact)
- `ingest_max_batch_bytes` / `max_concurrent_sends` (override the env defaults above)
- `circuit_failure_threshold` / `circuit_open_seconds` (override env; threshold `0` keeps the breaker off)
- `release` / `git_sha` — override `LUMONOX_RELEASE` / `LUMONOX_GIT_SHA` for this process (same trimming/caps as env); kwargs win when both are set.
- `telemetry_observer` — optional callable taking a small read-only dict per finished ingest POST (`kind="ingest_batch"`, `ok`, `events`, `attempt`, `duration_ms`, `queue_depth`, …). Must stay fast and must not raise; omit for zero overhead beyond a `None` check.
- `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s`

### `sdk_version` field

Each batch includes `sdk_version` resolved from installed distribution metadata (**`lumonox-sdk`**, then **`lumonox`**). Standard `pip install lumonox-sdk` installs therefore report a concrete version instead of `unknown`. If neither distribution is present (some editable layouts), the server may substitute its configured default.

### Compatibility

The SDK targets current **FastAPI** / **Starlette** / **httpx** versions pinned by this repo’s lockfile. The Django adapter targets **`django>=4.2`** (LTS) and is **async/ASGI-only** — classic synchronous WSGI Django is out of scope for v1. `fastapi` stays a required dependency even when you only use the Django adapter — it backs the default install, which ships the FastAPI adapter ready to use; `django` is pulled in only by the `[django]` extra. When upgrading major versions in your app, run your test suite against the Lumonox SDK release you deploy; treat minor/patch Lumonox bumps as drop-in unless release notes say otherwise.

## Request correlation IDs

- Incoming **`X-Request-ID`** or **`X-Correlation-ID`** (when **`X-Request-ID`** is absent) becomes the event **`request_id`** for that HTTP request.
- Responses include **`X-Request-ID`** when the client did not send one, so callers and downstream services can propagate the same value.
- **`capture_background_job(...)`** can omit **`correlated_request_id`** when it runs inside work that still has the middleware’s correlation context (for example right after handling a request).

## Security defaults

- Sensitive keys are scrubbed before send.
- **Headers and query strings are not captured unless explicitly enabled** (kwargs or env vars above)—opt in when debugging, not in production, unless you accept the PII risk.
- Middleware captures error context and re-raises original exceptions.

## Troubleshooting (“no events”)

1. Confirm `LUMONOX_API_KEY` and `LUMONOX_INGEST_URL` are both set for `lumonox()` (see startup `WARNING` when remote send is disabled).
2. Enable `LUMONOX_DEBUG=1` temporarily to surface queue drops or send failures on stderr.
3. Check dashboard server-scope filters (environment / service) vs the `environment` and `service_name` fields you send from the SDK.
4. Dashboard shows traffic but **requests/errors look empty** while DuckDB tools show rows: you likely opened a **different** DuckDB file than the API. Set `LUMONOX_DATA_DIR` or an absolute `LUMONOX_DUCKDB_PATH` on the backend and confirm startup logs (`Startup settings [event_store]: … duckdb_path=…`).

Canonical behavior and constraints are defined in `DEVELOPMENT.md`.
