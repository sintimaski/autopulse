# Synthetic Test App Fixture

This fixture provides a local FastAPI app and a deterministic traffic driver for manual AutoPulse dashboard testing.

## Components

- `synthetic_autopulse_config.py`: typed presets for how AutoPulse attaches (`SyntheticAutopulseFixture.one_line_embedded()`, `.separate_backend()`, `.from_env()`).
- `synthetic_test_app.py`: FastAPI app with 10 endpoints and controlled failure modes.
- `synthetic_load.py`: weighted request generator with periodic spikes and error bursts.

## Run

From repository root:

```bash
uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8010
```

Embedded mode also exposes local AutoPulse endpoints at:

- `http://localhost:8010/autopulse/ingest`
- `http://localhost:8010/autopulse/dashboard/*`
- `ws://localhost:8010/autopulse/dashboard/updates?token=…` (sends `subscribed` + `pong` to client `ping`; **`ingest` broadcasts only after batches hit this same server’s `/ingest`**)
- `http://localhost:8010/autopulse/ui/` (static assets when available)

In another terminal:

```bash
uv run python -m autopulse.fixtures.synthetic_load --base-url http://localhost:8010 --duration-seconds 120 --rps 8 --role-mode mixed
```

## Environment Variables

- `AUTOPULSE_MODE`: `embedded` (default) or `remote`.
- `AUTOPULSE_EMBEDDED_API_KEY` (embedded only): bearer for ingest + DB. If unset, SDK reads **`.env.autopulse`** then legacy `.autopulse/embedded-api-key`, else generates **`.env.autopulse`** (includes `NEXT_PUBLIC_*` for UI builds). `scripts/run_synthetic_stack.sh` sources it before `npm run build`. Startup ingest ping unless `AUTOPULSE_EMBEDDED_STARTUP_INGEST=0`.
- `AUTOPULSE_MOUNT_PREFIX`: embedded mount prefix (default `/autopulse`).
- `AUTOPULSE_DATABASE_URL`: relational metadata DB URL (default `sqlite+aiosqlite:///./autopulse.db`).
- `AUTOPULSE_EVENT_STORE`: raw log store backend (`duckdb` default, `sqlite` fallback).
- `AUTOPULSE_DUCKDB_PATH`: embedded DuckDB event file path (default `./.autopulse/events.duckdb`).
- `AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB`: max on-disk SQLite file size in MB (default `512` in embedded mode). Retention deletes oldest events across all projects until the file is under this cap. Set to `0` to turn off this global ceiling (dashboard per-project caps may still apply).
- `AUTOPULSE_FRONTEND_MODE`: embedded frontend mode (`static` default, `sidecar` optional).
- `AUTOPULSE_MODE=embedded` needs `autopulse-backend` (`pip install "autopulse[embedded]"` when both are on your index, or install both wheels from `./scripts/build_sdk_release_wheels.sh`).
- `AUTOPULSE_API_KEY`: project API key (`ap_live_...`) for remote ingest mode.
- `AUTOPULSE_INGEST_URL`: remote ingest URL (default `http://localhost:8000/ingest`).
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
