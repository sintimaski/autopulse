# Lumonox SDK (Python)

Lumonox SDK instruments a FastAPI app and sends request/error events to Lumonox with safe defaults.

## Install

| Goal | PyPI one-liner | Import / process |
|------|-----------------|------------------|
| **API + bundled dashboard UI** (ingest, dashboard, static export under `/lumonox/ui/`) | `pip install lumonox` | `from lumonox import mount_on_app` (or `lumonox_backend` / `uvicorn lumonox_backend.main:app`) |
| **Instrument your FastAPI app** (send-only SDK) | `pip install lumonox-sdk` | `from lumonox import lumonox` |
| **API + UI + SDK in one environment** | `pip install "lumonox-sdk[stack]"` | `from lumonox import lumonox, mount_on_app` |

`uv add` works the same (`uv add lumonox`, `uv add "lumonox-sdk[stack]"`, …).

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

```python
from fastapi import FastAPI
from lumonox import lumonox, monitor

app = FastAPI()
lumonox(app)  # recommended default
# monitor(app)  # backwards-compatible alias for existing integrations
```

`lumonox()` defaults **`environment` to `development`** so request events match common dashboard server-scope filters. Use `lumonox(app, environment="production")` when you need production labels.

By default, `lumonox()` (and `monitor()` for existing integrations) target a remote Lumonox project (set `LUMONOX_API_KEY` / `LUMONOX_INGEST_URL`). It uses bounded in-memory buffering, async background sending, and silent failure behavior so host apps stay healthy if Lumonox is unavailable.

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

`lumonox()` and `monitor()` support explicit kwargs for runtime behavior:

- `capture_headers` (default follows `LUMONOX_CAPTURE_HEADERS`, else **False**)
- `capture_query_params` (default follows `LUMONOX_CAPTURE_QUERY_PARAMS`, else **False**)
- `request_sample_rate` (float `0.0`-`1.0`, keeps 5xx/error capture unsampled)
- `ignore_path_prefixes` (tuple/list of path prefixes to skip, e.g. `("/health", "/ready")`)
- `scrub_keys` (additional sensitive keys to redact)
- `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s`

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
