# Backend Hardening Baseline Evidence (P0-T1)

- Date: 2026-05-11
- Scope: Baseline readiness evidence for backend hardening plan task `P0-T1`
- Runner: Local workspace commands from repo root

## Commands executed

1. `make check-python`
2. `bash ./scripts/release_gates.sh`

## Environment assumptions and variables

- Executed from: `/Users/dd/quests/autopulse`
- Python runtime observed in output: `Python 3.12.13`
- No explicit overrides were set for optional release gate env vars:
  - `LUMONOX_RELEASE_GATES_POSTGRES` (script default path is `0`)
  - `LUMONOX_RELEASE_GATES_E2E` (script default path is `0`)
- Note: `scripts/release_gates.sh` failed in backend tests before reaching optional Postgres/E2E branches or frontend gates.

## Baseline results

### A) `make check-python`

- `ruff check`: PASS
- `ruff format --check`: PASS
- `mypy`: PASS (`Success: no issues found in 141 source files`)
- `bandit`: PASS (`No issues identified`)
- `pytest`: FAIL
  - Totals: `1 failed, 271 passed, 125 skipped`
  - Failing test: `backend/tests/test_retention.py::test_duckdb_size_shrink_falls_back_to_widget_points`
  - Error:
    - `TypeError: _FakeStore.file_size_bytes() got an unexpected keyword argument 'duckdb_read_operation'`
  - Failure surface:
    - `backend/src/lumonox_backend/maintenance/retention_duckdb.py`
    - test monkeypatch helper in `backend/tests/test_retention.py`

### B) `scripts/release_gates.sh`

- Backend static checks: PASS (`ruff`, `format`, `mypy`, `bandit`)
- Backend tests: FAIL at the same retention test listed above
- Not reached due to early failure:
  - optional Postgres tests gate
  - frontend checks
  - optional E2E
  - phase5 smoke checks

## Skip and risk notes

- Current backend baseline includes `125 skipped` tests in default run; this should be treated as expected-but-visible risk until skip classes are reviewed in later tasks.
- Primary immediate blocker for green baseline is the retention test failure tied to wrapper keyword arguments passed through `run_duckdb_read_sync`.

## Task outcome mapping (`P0-T1` AC)

- AC1 (status and failures/skips captured): MET
- AC2 (env assumptions recorded): MET
- AC3 (artifact under `docs/plans/`): MET

## Next step

- Proceed to `P1-T1` (RBAC hardening) per phase order, while optionally opening a separate quick-fix task for the retention test regression to restore a green baseline gate.
