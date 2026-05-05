# Synthetic Test App Fixture

This fixture provides a local FastAPI app and a deterministic traffic driver for manual AutoPulse dashboard testing.

## Components

- `synthetic_autopulse_config.py`: typed presets for how AutoPulse attaches (`SyntheticAutopulseFixture.separate_backend()`, `.from_env()`).
- `synthetic_test_app.py`: FastAPI app with 10 endpoints and controlled failure modes.
- `synthetic_load.py`: weighted request generator with periodic spikes and error bursts.

## Run

**Recommended:** from repository root, `./scripts/run_synthetic_stack.sh` starts the backend on :8000 and the synthetic app on :8001 (see script output for dashboard URLs).

Manual two-process setup:

```bash
# Terminal A — backend
uv run python -m autopulse_backend.main

# Terminal B — synthetic app (set AUTOPULSE_API_KEY to your project ingest key)
export AUTOPULSE_INGEST_URL="http://127.0.0.1:8000/ingest"
export AUTOPULSE_API_KEY="<project API key>"
uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8001
```

Load generator (point at the synthetic app port you use):

```bash
uv run python -m autopulse.fixtures.synthetic_load \
  --base-url http://127.0.0.1:8001 \
  --duration-minutes 5 \
  --target-requests 200 \
  --role-mode mixed \
  --scenario realistic
```

## Environment Variables

- `AUTOPULSE_INGEST_URL`: ingest URL (default `http://127.0.0.1:8000/ingest` for standalone ``autopulse_backend``).
- `AUTOPULSE_API_KEY`: project API key (`ap_live_...`) for remote ingest.
- `AUTOPULSE_EVENT_STORE`: raw log store backend (`duckdb` default, `sqlite` fallback).
- `AUTOPULSE_DUCKDB_PATH`: DuckDB event file path. Relative values resolve under **`AUTOPULSE_DATA_DIR` / `AUTOPULSE_PROJECT_ROOT`**, else the monorepo checkout root (parent of `backend/`), not the shell cwd—see backend `resolve_autopulse_data_root` / `normalize_event_store_duckdb_path`. Prefer an **absolute** path or set `AUTOPULSE_DATA_DIR` in scripts so operators never open the wrong file.
- `AUTOPULSE_SQLITE_MAX_DB_FILE_MB`: max on-disk SQLite file size in MB for the backend (deprecated alias `AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB`). Retention deletes oldest events across all projects until the file is under this cap. Set to `0` to turn off this global ceiling (dashboard per-project caps may still apply).
- `AUTOPULSE_FRONTEND_MODE`: `static` (serve export from the backend) or `sidecar` (Next `npm run dev`; default for `scripts/run_synthetic_stack.sh`). With sidecar, set `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` to an absolute API URL (see `AUTOPULSE_SIDECAR_API_BASE_URL` in that script).
- `AUTOPULSE_SERVICE_NAME`: service label (default `synthetic-test-api`).
- `AUTOPULSE_ENVIRONMENT`: environment label (default `dev`).
- `AUTOPULSE_BATCH_SIZE`: SDK batch size override.
- `AUTOPULSE_FLUSH_INTERVAL_S`: SDK flush interval override.
- `AUTOPULSE_DEBUG`: set to `1`/`true` to enable SDK debug logs.

## Manual Verification Checklist

- Volume chart reflects spikes every configured spike interval.
- Error rate increases during burst windows and includes 4xx/5xx.
- `/boom` failures create grouped errors with stack traces.
- Auth denials are visible as 401/403 patterns.
- `/reports/daily` slow/timeout behavior is visible in latency panels.
