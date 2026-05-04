#!/usr/bin/env bash
# Split-stack local dev: backend (uvicorn) + Next dev server, with one canonical DuckDB file.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Loading backend/.env (if present)…"
if [[ -f backend/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source backend/.env
  set +a
fi

export AUTOPULSE_DATA_DIR="${AUTOPULSE_DATA_DIR:-$ROOT_DIR}"
export AUTOPULSE_DUCKDB_PATH="${AUTOPULSE_DUCKDB_PATH:-$AUTOPULSE_DATA_DIR/.autopulse/events.duckdb}"

echo "AUTOPULSE_DATA_DIR=${AUTOPULSE_DATA_DIR}"
echo "AUTOPULSE_DUCKDB_PATH=${AUTOPULSE_DUCKDB_PATH}"
echo
echo "Next steps (two terminals, repo root):"
echo "  1) uv run python -m autopulse_backend.main   # or uvicorn from backend with same env"
echo "  2) npm --prefix frontend install && npm --prefix frontend run dev"
echo "Set frontend NEXT_PUBLIC_AUTOPULSE_API_BASE_URL to match your API (see README)."
