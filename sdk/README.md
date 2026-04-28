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
- `AUTOPULSE_ENDPOINT`
- `AUTOPULSE_FLUSH_INTERVAL_SECONDS`
- `AUTOPULSE_BATCH_MAX_EVENTS`
- `AUTOPULSE_MAX_QUEUE_SIZE`
- `AUTOPULSE_DEBUG`

## Security defaults

- Sensitive keys are scrubbed before send.
- Capture is conservative by default.
- Middleware captures error context and re-raises original exceptions.

Canonical behavior and constraints are defined in `DEVELOPMENT.md`.
