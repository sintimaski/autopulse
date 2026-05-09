#!/usr/bin/env bash
# Full release gate — keep in sync with .github/workflows/ci.yml expectations.
#
# Critical-path manifest (always runs here unless noted):
#   - Backend: ruff check/format, mypy, bandit, pytest (SQLite baseline)
#   - Frontend: npm audit (high), lint, typecheck, vitest, next build, bundle budget
#   - Jobs smoke: alerts-once, retention-once
# Optional env (same split as CI jobs):
#   - LUMONOX_RELEASE_GATES_POSTGRES=1 → uv run pytest backend/tests
#   - LUMONOX_RELEASE_GATES_E2E=1 → npm --prefix frontend run test:e2e
set -euo pipefail

echo "[release-gates] backend static checks"
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/lumonox backend/src/lumonox_backend

echo "[release-gates] backend tests"
uv run pytest

# Optional Postgres metadata path gate:
# - CI policy runs a dedicated Postgres backend test job (.github/workflows/ci.yml).
# - Local release gate keeps SQLite/full path as default and allows explicit Postgres run.
if [[ "${LUMONOX_RELEASE_GATES_POSTGRES:-0}" == "1" ]]; then
  echo "[release-gates] postgres optional-path tests"
  uv run pytest backend/tests -q
else
  echo "[release-gates] postgres optional-path tests skipped (set LUMONOX_RELEASE_GATES_POSTGRES=1 to run)"
fi

echo "[release-gates] frontend checks"
npm --prefix frontend audit --audit-level=high
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
npm --prefix frontend run check:bundle-budget

# Optional browser smoke path gate:
# - CI policy runs browser smoke in a dedicated job (.github/workflows/ci.yml).
# - Local release gate keeps browser smoke optional because Playwright browser install
#   can be heavyweight on contributor machines.
if [[ "${LUMONOX_RELEASE_GATES_E2E:-0}" == "1" ]]; then
  echo "[release-gates] browser smoke e2e"
  npm --prefix frontend run test:e2e
else
  echo "[release-gates] browser smoke e2e skipped (set LUMONOX_RELEASE_GATES_E2E=1 to run)"
fi

echo "[release-gates] phase5 smoke checks"
uv run python -m lumonox_backend.jobs alerts-once >/dev/null
uv run python -m lumonox_backend.jobs retention-once >/dev/null

echo "[release-gates] all checks passed"
