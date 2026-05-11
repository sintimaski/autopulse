#!/usr/bin/env bash
# Sequential local mirror of .github/workflows/ci.yml (single machine).
#
# Default: python-sqlite job + frontend job (matches CI split; no Postgres, no Playwright).
#
# Optional (same spirit as extra CI jobs):
#   LUMONOX_CI_POSTGRES=1  — requires BACKEND_TEST_DATABASE_URL=postgresql+asyncpg://...
#                            (and DATABASE_URL if you use a different primary DB URL)
#   LUMONOX_CI_E2E=1       — Playwright browser-smoke (run once:
#                            cd frontend && npx playwright install --with-deps chromium)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[ci-local] job: python-sqlite"
(
  export DATABASE_URL="sqlite+aiosqlite://${ROOT}/lumonox_ci.db"
  export BACKEND_TEST_DATABASE_URL="sqlite+aiosqlite://${ROOT}/lumonox_ci_test.db"
  export LUMONOX_EVENT_STORE="sqlite"
  export LUMONOX_EVENT_PLANE_MODE="duckdb_single_writer"
  export JOBS_ENABLE_SCHEDULER="false"
  export DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS="false"
  export DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK="true"
  export LUMONOX_SQLITE_SIZE_RETENTION_ONLY="false"
  export INGEST_ASYNC_AGGREGATE_ENABLED="false"
  export LUMONOX_DUCKDB_PATH="${ROOT}/.lumonox/ci-events.duckdb"

  uv run ruff check .
  uv run ruff format --check .
  uv run mypy
  bash scripts/pre_commit_lumonox_wheel_smoke.sh
  uv run bandit -c pyproject.toml -r sdk/src/lumonox backend/src/lumonox_backend
  uv run pip-audit
  uv run pytest --cov=lumonox --cov=lumonox_backend --cov-report=term-missing
  uv build --package lumonox-sdk --wheel -o packaging-dist && rm -rf packaging-dist
  uv run python -m lumonox_backend.jobs alerts-once >/dev/null
  uv run python -m lumonox_backend.jobs retention-once >/dev/null
)

if [[ "${LUMONOX_CI_POSTGRES:-0}" == "1" ]]; then
  echo "[ci-local] job: python-postgres"
  if [[ "${BACKEND_TEST_DATABASE_URL:-}" != postgresql* ]]; then
    echo "[ci-local] LUMONOX_CI_POSTGRES=1 requires BACKEND_TEST_DATABASE_URL=postgresql+asyncpg://..." >&2
    exit 1
  fi
  _pg_db_url="${DATABASE_URL:-}"
  if [[ "${_pg_db_url}" != postgresql* ]]; then
    _pg_db_url="${BACKEND_TEST_DATABASE_URL}"
  fi
  (
    export DATABASE_URL="${_pg_db_url}"
    export BACKEND_TEST_DATABASE_URL
    export LUMONOX_EVENT_STORE="sqlite"
    export LUMONOX_EVENT_PLANE_MODE="duckdb_single_writer"
    export LUMONOX_DUCKDB_PATH="${ROOT}/.lumonox/ci-events-postgres.duckdb"
    export JOBS_ENABLE_SCHEDULER="false"
    export INGEST_ASYNC_AGGREGATE_ENABLED="false"
    export DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS="false"
    export DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK="true"

    uv run pytest backend/tests/test_ingest.py::test_ingest_idempotency_key_replays_accepted_without_duplicate_events -q
    uv run pytest backend/tests -q
  )
else
  echo "[ci-local] job: python-postgres skipped (set LUMONOX_CI_POSTGRES=1 and Postgres URLs to run)"
fi

echo "[ci-local] job: frontend"
(
  cd "${ROOT}/frontend"
  npm ci
  npm audit --audit-level=high
  npm run lint
  npm run typecheck
  npm run test
  npm run build
  npm run check:bundle-budget
)

_wheel_tmp="$(mktemp -d "${TMPDIR:-/tmp}/ap-ci-local-wheel.XXXXXX")"
cleanup_wheel_tmp() {
  rm -rf "${_wheel_tmp}"
}
trap cleanup_wheel_tmp EXIT

echo "[ci-local] backend wheel includes dashboard static export"
uv build backend -o "${_wheel_tmp}"
unzip -l "${_wheel_tmp}"/lumonox-*-py3-none-any.whl | grep -Fq "lumonox_backend/dashboard_static/index.html"

if [[ "${LUMONOX_CI_E2E:-0}" == "1" ]]; then
  echo "[ci-local] job: browser-smoke"
  (
    export DATABASE_URL="sqlite+aiosqlite://${ROOT}/lumonox_e2e.db"
    export BACKEND_TEST_DATABASE_URL="sqlite+aiosqlite://${ROOT}/lumonox_e2e_test.db"
    export LUMONOX_EVENT_STORE="duckdb"
    export LUMONOX_DUCKDB_PATH="${ROOT}/.lumonox/e2e-events.duckdb"
    export LUMONOX_FRONTEND_STATIC_DIR="${ROOT}/frontend/out"
    export DASHBOARD_AUTH_ENABLED="true"
    export DASHBOARD_AUTH_ALLOWED_EMAIL="e2e@example.com"
    export DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN="true"
    export INTERNAL_METRICS_BEARER_TOKEN="e2e-internal-token"
    export E2E_BASE_URL="http://127.0.0.1:8000/lumonox/ui"
    export E2E_DASHBOARD_EMAIL="e2e@example.com"

    cd "${ROOT}/frontend"
    npx playwright install --with-deps chromium

    UVICORN_PID=""
    on_exit_uvicorn() {
      if [[ -n "${UVICORN_PID}" ]] && kill -0 "${UVICORN_PID}" 2>/dev/null; then
        kill "${UVICORN_PID}" 2>/dev/null || true
        wait "${UVICORN_PID}" 2>/dev/null || true
      fi
    }
    trap on_exit_uvicorn EXIT

    cd "${ROOT}"
    uv run uvicorn lumonox_backend.main:app --app-dir backend/src --host 127.0.0.1 --port 8000 --log-level info &
    UVICORN_PID=$!

    _ready=0
    for _i in $(seq 1 60); do
      if curl -sf http://127.0.0.1:8000/ready >/dev/null; then
        _ready=1
        break
      fi
      sleep 1
    done
    if [[ "${_ready}" -ne 1 ]]; then
      echo "[ci-local] backend did not become ready" >&2
      exit 1
    fi

    cd "${ROOT}/frontend"
    npm run test:e2e
  )
else
  echo "[ci-local] job: browser-smoke skipped (set LUMONOX_CI_E2E=1 to run Playwright)"
fi

echo "[ci-local] all requested checks passed"
