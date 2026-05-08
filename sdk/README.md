# AutoPulse SDK (Python)

AutoPulse SDK instruments a FastAPI app and sends request/error events to AutoPulse with safe defaults.

## Install

| Goal | PyPI one-liner | Import / process |
|------|-----------------|------------------|
| **API + bundled dashboard UI** (ingest, dashboard, static export under `/autopulse/ui/`) | `pip install autopulse-api` | `import autopulse_backend` · run `uvicorn autopulse_backend.main:app` |
| **Instrument your FastAPI app** (send-only SDK) | `pip install autopulse-sdk` | `from autopulse import autopulse` |
| **API + UI + SDK in one environment** | `pip install "autopulse-sdk[stack]"` | both of the above |

`uv add` works the same (`uv add autopulse-api`, `uv add "autopulse-sdk[stack]"`, …).

**From a git checkout** (offline wheels from repo root):

```bash
./scripts/build_sdk_release_wheels.sh   # writes dist/wheels/*.whl
pip install dist/wheels/autopulse_api-*.whl dist/wheels/autopulse_sdk-*.whl
```

## Publish to PyPI

Artifacts are standard **wheel + sdist** from the workspace root (`hatchling` via `uv build`):

```bash
uv build --package autopulse-sdk -o dist/pypi-sdk
python -m pip install twine   # once
twine check dist/pypi-sdk/*
twine upload dist/pypi-sdk/*
```

**Recommended:** use [trusted publishing](https://docs.pypi.org/trusted-publishers/) from GitHub Actions instead of storing a long-lived PyPI token in CI secrets:

- **SDK:** `.github/workflows/publish-autopulse-sdk-pypi.yml` → project **`autopulse-sdk`**
- **API + bundled UI:** `.github/workflows/publish-autopulse-api-pypi.yml` → project **`autopulse-api`**

**On `main`:** the SDK workflow runs when `sdk/pyproject.toml`, `sdk/src/**`, `sdk/README.md`, or `sdk/LICENSE` change. The **`autopulse`** workflow runs when `backend/pyproject.toml`, `backend/src/**`, or `frontend/**` change. Both upload **only when** the corresponding `[project] version` is **not already** on PyPI.

**`autopulse-sdk[stack]` on PyPI:** publish **`autopulse-api`** first (or same release train) so the extra can resolve **`autopulse-api>=0.1.5`**.

**One-time on PyPI:** create projects **`autopulse-sdk`** and **`autopulse-api`**, add trusted publishers for each workflow, then merge version bumps or run workflows manually.

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
