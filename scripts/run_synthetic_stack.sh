#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Loading backend/.env…"
set -a
# shellcheck disable=SC1091
source backend/.env
set +a

if [ -f .env.autopulse ]; then
  echo "Loading .env.autopulse (overrides NEXT_PUBLIC_* / embedded key from first SDK boot)…"
  set -a
  # shellcheck disable=SC1091
  source .env.autopulse
  set +a
fi

FRONTEND_DIR="$ROOT_DIR/frontend"
if [[ ! -f "$FRONTEND_DIR/node_modules/next/dist/bin/next" ]]; then
  echo "error: frontend dependencies missing (no Next.js CLI)." >&2
  echo "  Run: npm --prefix frontend install" >&2
  exit 1
fi
echo "Building frontend…"
npm --prefix frontend run build

# Force DuckDB for synthetic-stack runs so raw events/widget points never land in SQLite.
export AUTOPULSE_EVENT_STORE="duckdb"
export AUTOPULSE_DUCKDB_PATH="${AUTOPULSE_DUCKDB_PATH:-./.autopulse/events.duckdb}"

echo "DATABASE_URL=${DATABASE_URL:-<unset>}"
echo "AUTOPULSE_EVENT_STORE=${AUTOPULSE_EVENT_STORE}"
echo "AUTOPULSE_DUCKDB_PATH=${AUTOPULSE_DUCKDB_PATH}"
echo "Starting: uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8000 --log-level info"
exec uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8000 --log-level info
