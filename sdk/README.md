# AutoPulse SDK (Python)

AutoPulse SDK instruments a FastAPI app and sends request/error events to AutoPulse with safe defaults.

## Install

```bash
pip install autopulse
```

## Minimal integration

```python
from autopulse import monitor

monitor(app)
```

By default, the SDK uses bounded in-memory buffering, async background sending, and silent failure behavior so host apps stay healthy if AutoPulse is unavailable.

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
