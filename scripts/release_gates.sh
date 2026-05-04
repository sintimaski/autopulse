#!/usr/bin/env bash
set -euo pipefail

echo "[release-gates] backend static checks"
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -c pyproject.toml -r sdk/src/autopulse -r backend/src/autopulse_backend

echo "[release-gates] backend tests"
uv run pytest

echo "[release-gates] frontend checks"
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
AUTOPULSE_BUNDLE_SKIP_NPM_CI=1 bash scripts/bundle_embedded_dashboard_ui.sh

echo "[release-gates] phase5 smoke checks"
uv run python -m autopulse_backend.jobs alerts-once >/dev/null
uv run python -m autopulse_backend.jobs retention-once >/dev/null

echo "[release-gates] all checks passed"
