#!/usr/bin/env bash
# One-line embedded synthetic stack: FastAPI app + DuckDB event store + Next dev sidecar
# (same UX as remote split stack, still a single `exec` from this script).
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

FRONTEND_MODE="${AUTOPULSE_FRONTEND_MODE:-sidecar}"
export AUTOPULSE_FRONTEND_MODE="$FRONTEND_MODE"

if [[ "$FRONTEND_MODE" == "static" ]]; then
  echo "Building frontend (static export for embedded /ui)…"
  npm --prefix frontend run build
else
  echo "Frontend: Next dev sidecar (AUTOPULSE_FRONTEND_MODE=$FRONTEND_MODE); skipping static export build."
  _ap_mount="${AUTOPULSE_MOUNT_PREFIX:-/autopulse}"
  echo "  Dashboard UI (Next):  http://localhost:3000/"
  echo "  API (FastAPI):        http://127.0.0.1:8000${_ap_mount}/  (dashboard also works at http://127.0.0.1:8000${_ap_mount}/ui/ after static build)"
  echo "  Tip: UI on port 8000 only → run with AUTOPULSE_FRONTEND_MODE=static (script runs npm build) then open …/ui/"
  # Cross-origin browser fetches require an absolute API origin (not same-origin /autopulse on :3000).
  # If AUTOPULSE_SIDECAR_API_BASE_URL is set to an origin only (e.g. http://127.0.0.1:8000), append the
  # embedded mount prefix so paths like /dashboard/* resolve (they live under /autopulse/dashboard/*).
  if [[ -n "${AUTOPULSE_SIDECAR_API_BASE_URL:-}" ]]; then
    _ap_sidecar="${AUTOPULSE_SIDECAR_API_BASE_URL}"
  else
    _ap_sidecar="http://127.0.0.1:8000${_ap_mount}"
  fi
  _ap_sidecar="${_ap_sidecar%/}"
  if [[ "$_ap_sidecar" =~ ^https?://[^/]+$ ]]; then
    _ap_sidecar="${_ap_sidecar}${_ap_mount}"
  fi
  export NEXT_PUBLIC_AUTOPULSE_API_BASE_URL="$_ap_sidecar"
  echo "NEXT_PUBLIC_AUTOPULSE_API_BASE_URL=${NEXT_PUBLIC_AUTOPULSE_API_BASE_URL}"
  export NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN="${NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN:-http://127.0.0.1:8000}"
  echo "NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN=${NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN}"
  # Next 16 blocks dev-only routes (e.g. /_next/webpack-hmr) from non-localhost origins unless listed here.
  if [[ -z "${AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS:-}" ]] && [[ "$(uname -s)" == "Darwin" ]]; then
    _ap_lan_ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
    if [[ -n "$_ap_lan_ip" ]]; then
      export AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS="$_ap_lan_ip"
      echo "AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS=${AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS} (auto en0; override in .env if HMR still blocked)"
    fi
  fi
fi

# Force DuckDB for synthetic-stack runs so raw events/widget points never land in SQLite.
export AUTOPULSE_EVENT_STORE="duckdb"
# Pin data root + explicit DuckDB file (backend also normalizes relative AUTOPULSE_DUCKDB_PATH
# against the repo root by default—this export keeps scripts and operators aligned).
export AUTOPULSE_DATA_DIR="${AUTOPULSE_DATA_DIR:-$ROOT_DIR}"
export AUTOPULSE_DUCKDB_PATH="${AUTOPULSE_DUCKDB_PATH:-$AUTOPULSE_DATA_DIR/.autopulse/events.duckdb}"

echo "DATABASE_URL=${DATABASE_URL:-<unset>}"
echo "AUTOPULSE_EVENT_STORE=${AUTOPULSE_EVENT_STORE}"
echo "AUTOPULSE_DATA_DIR=${AUTOPULSE_DATA_DIR}"
echo "AUTOPULSE_DUCKDB_PATH=${AUTOPULSE_DUCKDB_PATH}"
echo "AUTOPULSE_FRONTEND_MODE=${AUTOPULSE_FRONTEND_MODE}"
echo "Starting: uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8000 --log-level info"
exec uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8000 --log-level info
