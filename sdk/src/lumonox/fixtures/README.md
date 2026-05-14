# Synthetic Test App Fixture

This fixture provides a local FastAPI app and a deterministic traffic driver for manual Lumonox dashboard testing.

## Components

- `synthetic_lumonox_config.py`: typed presets for how Lumonox attaches (`SyntheticLumonoxFixture.separate_backend()`, `.from_env()`).
- `synthetic_test_app.py`: FastAPI app with 10 endpoints and controlled failure modes.
- `synthetic_load.py`: weighted request generator with periodic spikes and error bursts.
- `synthetic_django_app.py`: minimum-viable Django app (`/health/`, `/users/<id>/`, `/boom/`) exercising the `lumonox.django` adapter. `create_monitored_asgi_app()` is the runnable uvicorn factory.

## Run

**Recommended:** from repository root, `./scripts/run_synthetic_stack.sh` starts the backend on :8000 and the synthetic app on :8001 (see script output for dashboard URLs).

Manual two-process setup:

```bash
# Terminal A — backend
uv run python -m lumonox_backend.main

# Terminal B — synthetic app (set LUMONOX_API_KEY to your project ingest key)
export LUMONOX_INGEST_URL="http://127.0.0.1:8000/ingest"
export LUMONOX_API_KEY="<project API key>"
uv run uvicorn lumonox.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8001
```

Load generator (point at the synthetic app port you use):

```bash
uv run python -m lumonox.fixtures.synthetic_load \
  --base-url http://127.0.0.1:8001 \
  --duration-minutes 5 \
  --target-requests 200 \
  --role-mode mixed \
  --scenario realistic
```

### Django variant

`./scripts/run_synthetic_django_stack.sh` runs the same stack with the Django
fixture (`synthetic_django_app.py`) as the :8001 sample app instead of the
FastAPI one. It is a thin wrapper that points the synthetic-app slot at the
Django ASGI factory and delegates to `run_synthetic_stack.sh`, so the backend,
DuckDB defaults, and frontend build are unchanged. Requires Django to be
importable under `uv run` (workspace dev group, or `lumonox-sdk[django]`).

The Django fixture is intentionally minimal (3 routes), so the FastAPI-tuned
`synthetic_load` generator does not apply — use the curl-loop driver instead:

```bash
./scripts/examples/synthetic_django_load_demo.sh
```

Manual two-process setup (Django):

```bash
# Terminal A — backend (see FastAPI setup above)
# Terminal B — synthetic Django app
export LUMONOX_INGEST_URL="http://127.0.0.1:8000/ingest"
export LUMONOX_API_KEY="<project API key>"
uv run uvicorn lumonox.fixtures.synthetic_django_app:create_monitored_asgi_app \
  --factory --host 0.0.0.0 --port 8001
```

## Environment Variables

- `LUMONOX_INGEST_URL`: ingest URL (default `http://127.0.0.1:8000/ingest` for standalone ``lumonox_backend``).
- `LUMONOX_API_KEY`: project API key (`ap_live_...`) for remote ingest.
- `LUMONOX_EVENT_STORE`: raw log store backend (`duckdb` default, `sqlite` fallback).
- `LUMONOX_DUCKDB_PATH`: DuckDB event file path. Relative values resolve under **`LUMONOX_DATA_DIR` / `LUMONOX_PROJECT_ROOT`**, else the monorepo checkout root (parent of `backend/`), not the shell cwd—see backend `resolve_lumonox_data_root` / `normalize_event_store_duckdb_path`. Prefer an **absolute** path or set `LUMONOX_DATA_DIR` in scripts so operators never open the wrong file.
- `LUMONOX_SQLITE_MAX_DB_FILE_MB`: max on-disk SQLite file size in MB for the backend (deprecated alias `LUMONOX_EMBEDDED_MAX_DB_SIZE_MB`). Retention deletes oldest events across all projects until the file is under this cap. Set to `0` to turn off this global ceiling (dashboard per-project caps may still apply).
- `LUMONOX_FRONTEND_MODE`: `static` (serve export from the backend) or `sidecar` (Next `npm run dev`; default for `scripts/run_synthetic_stack.sh`). With sidecar, set `NEXT_PUBLIC_LUMONOX_API_BASE_URL` to an absolute API URL (see `LUMONOX_SIDECAR_API_BASE_URL` in that script).
- `LUMONOX_SERVICE_NAME`: service label (default `synthetic-test-api`).
- `LUMONOX_ENVIRONMENT`: environment label (default `dev`).
- `LUMONOX_BATCH_SIZE`: SDK batch size override.
- `LUMONOX_FLUSH_INTERVAL_S`: SDK flush interval override.
- `LUMONOX_DEBUG`: set to `1`/`true` to enable SDK debug logs.

## Manual Verification Checklist

- Volume chart reflects spikes every configured spike interval.
- Error rate increases during burst windows and includes 4xx/5xx.
- `/boom` failures create grouped errors with stack traces.
- Auth denials are visible as 401/403 patterns.
- `/reports/daily` slow/timeout behavior is visible in latency panels.
