# CI reliability matrix

The default `python-sqlite` CI job pins conservative runtime flags so the full pytest
suite stays deterministic (no in-process alert ticker, inline SQL aggregates).

Production-like combinations are exercised in a **separate** job so regressions in these
paths surface without slowing every PR:

| Surface | Default CI (`python-sqlite`) | Matrix job (`python-sqlite-reliability-matrix`) |
|--------|------------------------------|--------------------------------------------------|
| `JOBS_ENABLE_SCHEDULER` | `false` | `true` (long intervals) |
| `INGEST_ASYNC_AGGREGATE_ENABLED` | `false` | `true` |
| `BACKEND_TEST_DATABASE_URL` | unset (pytest temp DB + conftest pins) | set (conftest does not override scheduler/aggregate) |

## Job location

See `.github/workflows/ci.yml` → job `python-sqlite-reliability-matrix`.

## Local reproduction

```bash
export DATABASE_URL="sqlite+aiosqlite:///./lumonox_matrix.db"
export BACKEND_TEST_DATABASE_URL="sqlite+aiosqlite:///./lumonox_matrix_test.db"
export LUMONOX_EVENT_STORE=sqlite
export LUMONOX_EVENT_PLANE_MODE=duckdb_single_writer
export LUMONOX_DUCKDB_PATH="./.lumonox/matrix-events.duckdb"
export JOBS_ENABLE_SCHEDULER=true
export INGEST_ASYNC_AGGREGATE_ENABLED=true
export JOBS_ALERT_INTERVAL_SECONDS=3600
export JOBS_RETENTION_INTERVAL_SECONDS=3600
export DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS=false
export DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK=true
uv run pytest \
  backend/tests/test_event_plane_parity.py \
  backend/tests/test_event_plane_read_path.py \
  backend/tests/test_ci_reliability_matrix.py \
  backend/tests/test_ingest.py::test_ingest_async_aggregate_sync_fallback_when_enqueue_returns_false \
  -q
```
