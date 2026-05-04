# AutoPulse SDK (Python)

AutoPulse SDK instruments a FastAPI app and sends request/error events to AutoPulse with safe defaults.

## Install

```bash
pip install autopulse
```

**From a git checkout** (with the backend in the same workspace):

```bash
./scripts/build_sdk_release_wheels.sh   # from repo root; writes dist/wheels/*.whl
pip install dist/wheels/autopulse_backend-*.whl dist/wheels/autopulse-*.whl
```

## Integration

```python
from fastapi import FastAPI
from autopulse import autopulse, monitor

app = FastAPI()
autopulse(app)  # recommended default
# monitor(app)  # backwards-compatible alias for existing integrations
```

`autopulse()` defaults **`environment` to `development`** so request events match common dashboard server-scope filters. Use `autopulse(app, environment="production")` when you need production labels.

By default, `autopulse()` (and `monitor()` for existing integrations) target a remote AutoPulse project (set `AUTOPULSE_API_KEY` / `AUTOPULSE_INGEST_URL`). It uses bounded in-memory buffering, async background sending, and silent failure behavior so host apps stay healthy if AutoPulse is unavailable.

If **either** variable is missing, the sender stays off: middleware still runs, but **no events are enqueued** (minimal overhead). A **one-time `WARNING`** is emitted on process startup so misconfiguration is obvious without breaking the host app.

## Key runtime controls

- `AUTOPULSE_API_KEY`
- `AUTOPULSE_INGEST_URL` (or `AUTOPULSE_ENDPOINT`)
- `AUTOPULSE_FLUSH_INTERVAL_SECONDS`
- `AUTOPULSE_BATCH_MAX_EVENTS`
- `AUTOPULSE_MAX_QUEUE_SIZE`
- `AUTOPULSE_DEBUG`
- `AUTOPULSE_REQUEST_SAMPLE_RATE` (`0.0`-`1.0`; default `1.0`)
- `AUTOPULSE_IGNORE_PATH_PREFIXES` (comma-separated, default `/health,/ready`)
- `AUTOPULSE_CAPTURE_HEADERS` — when `true`/`1`/`yes`, capture request headers in events (default **off** for production-safe privacy).
- `AUTOPULSE_CAPTURE_QUERY_PARAMS` — when truthy, capture query parameters (default **off**).

`autopulse()` and `monitor()` support explicit kwargs for runtime behavior:

- `capture_headers` (default follows `AUTOPULSE_CAPTURE_HEADERS`, else **False**)
- `capture_query_params` (default follows `AUTOPULSE_CAPTURE_QUERY_PARAMS`, else **False**)
- `request_sample_rate` (float `0.0`-`1.0`, keeps 5xx/error capture unsampled)
- `ignore_path_prefixes` (tuple/list of path prefixes to skip, e.g. `("/health", "/ready")`)
- `scrub_keys` (additional sensitive keys to redact)
- `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s`

## Security defaults

- Sensitive keys are scrubbed before send.
- **Headers and query strings are not captured unless explicitly enabled** (kwargs or env vars above)—opt in when debugging, not in production, unless you accept the PII risk.
- Middleware captures error context and re-raises original exceptions.

## Troubleshooting (“no events”)

1. Confirm `AUTOPULSE_API_KEY` and `AUTOPULSE_INGEST_URL` are both set for `autopulse()` (see startup `WARNING` when remote send is disabled).
2. Enable `AUTOPULSE_DEBUG=1` temporarily to surface queue drops or send failures on stderr.
3. Check dashboard server-scope filters (environment / service) vs the `environment` and `service_name` fields you send from the SDK.
4. Dashboard shows traffic but **requests/errors look empty** while DuckDB tools show rows: you likely opened a **different** DuckDB file than the API. Set `AUTOPULSE_DATA_DIR` or an absolute `AUTOPULSE_DUCKDB_PATH` on the backend and confirm startup logs (`Startup settings [event_store]: … duckdb_path=…`).

Canonical behavior and constraints are defined in `DEVELOPMENT.md`.
