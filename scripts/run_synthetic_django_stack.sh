#!/usr/bin/env bash
# Django variant of run_synthetic_stack.sh: Lumonox backend (:8000) + synthetic
# *Django* sample app (:8001) + default Next sidecar.
#
# The synthetic sample app is the only thing that differs from the FastAPI
# stack — backend, DuckDB-first storage defaults, and the frontend build are
# identical — so this just points the synthetic-app slot at the Django fixture
# and delegates to run_synthetic_stack.sh (which keeps the DuckDB defaults).
#
# Prerequisites: Django must be importable under `uv run` (it ships in the
# workspace dev group; for a published install use `lumonox-sdk[django]`).
# Set LUMONOX_API_KEY (or NEXT_PUBLIC_LUMONOX_API_KEY) so the app can ingest.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The Django entry point is a uvicorn factory (`--factory`): importing the
# fixture module stays side-effect-free, so the SDK unit tests that do
# `from ... import create_asgi_app` are unaffected.
export LUMONOX_SYNTHETIC_APP_TARGET="lumonox.fixtures.synthetic_django_app:create_monitored_asgi_app"
export LUMONOX_SYNTHETIC_APP_UVICORN_ARGS="--factory"
export LUMONOX_SYNTHETIC_APP_LABEL="synthetic Django app"
# The Django fixture's health route is `/health/` (no CommonMiddleware → no
# APPEND_SLASH redirect from `/health`).
export LUMONOX_SYNTHETIC_APP_HEALTH_PATH="/health/"
export LUMONOX_SERVICE_NAME="${LUMONOX_SERVICE_NAME:-synthetic-django-api}"

exec "$ROOT_DIR/scripts/run_synthetic_stack.sh"
