#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Building frontend..."
npm --prefix frontend run build

echo "Loading backend/.env and starting synthetic app..."
set -a
# shellcheck disable=SC1091
source backend/.env
set +a

# Force DuckDB for synthetic-stack runs so raw events/widget points never land in SQLite.
export AUTOPULSE_EVENT_STORE="duckdb"
export AUTOPULSE_DUCKDB_PATH="${AUTOPULSE_DUCKDB_PATH:-./.autopulse/events.duckdb}"

echo "DATABASE_URL=${DATABASE_URL:-<unset>}"
echo "AUTOPULSE_EVENT_STORE=${AUTOPULSE_EVENT_STORE}"
echo "AUTOPULSE_DUCKDB_PATH=${AUTOPULSE_DUCKDB_PATH}"
echo "Starting: uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8010 --log-level info"
exec uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8010 --log-level info
