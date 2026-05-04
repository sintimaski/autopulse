#!/usr/bin/env bash
# Local integration: AutoPulse backend (:8000) + synthetic sample app (:8001) + optional Next sidecar.
# Always runs `npm --prefix frontend run build` first (static export → frontend/out/).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Loading backend/.env…"
set -a
# shellcheck disable=SC1091
source backend/.env
set +a

if [ -f .env.autopulse ]; then
  echo "Loading .env.autopulse (overrides NEXT_PUBLIC_* / ingest key for local UI builds)…"
  set -a
  # shellcheck disable=SC1091
  source .env.autopulse
  set +a
fi

# ``npm run build`` inlines ``NEXT_PUBLIC_*`` at compile time. Force the standalone-backend API
# origin here so stale ``/autopulse`` API bases from older .env files cannot bake into ``frontend/out``.
export NEXT_PUBLIC_AUTOPULSE_API_BASE_URL="${NEXT_PUBLIC_AUTOPULSE_API_BASE_URL:-http://127.0.0.1:8000}"
export NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN="${NEXT_PUBLIC_AUTOPULSE_DEV_API_ORIGIN:-http://127.0.0.1:8000}"
echo "For frontend build: NEXT_PUBLIC_AUTOPULSE_API_BASE_URL=${NEXT_PUBLIC_AUTOPULSE_API_BASE_URL}"

FRONTEND_DIR="$ROOT_DIR/frontend"
if [[ ! -f "$FRONTEND_DIR/node_modules/next/dist/bin/next" ]]; then
  echo "error: frontend dependencies missing (no Next.js CLI)." >&2
  echo "  Run: npm --prefix frontend install" >&2
  exit 1
fi

echo "Building frontend (Next static export → frontend/out/)…"
npm --prefix frontend run build

export AUTOPULSE_FRONTEND_STATIC_DIR="${AUTOPULSE_FRONTEND_STATIC_DIR:-$ROOT_DIR/frontend/out}"

FRONTEND_MODE="${AUTOPULSE_FRONTEND_MODE:-sidecar}"
export AUTOPULSE_FRONTEND_MODE="$FRONTEND_MODE"

if [[ "$FRONTEND_MODE" == "static" ]]; then
  echo "AUTOPULSE_FRONTEND_MODE=static: dashboard export is served from the backend under …/autopulse/ui/."
else
  echo "Frontend: Next dev sidecar (AUTOPULSE_FRONTEND_MODE=$FRONTEND_MODE); static export was built above for the backend mount."
  _ui_mount="${AUTOPULSE_MOUNT_PREFIX:-/autopulse}"
  echo "  Dashboard UI (Next):  http://localhost:3000/"
  echo "  API (backend):        http://127.0.0.1:8000 (JSON under /dashboard and /autopulse/dashboard; ingest at /ingest and /autopulse/ingest; static UI at http://127.0.0.1:8000${_ui_mount}/ui/ when mounted)"
  echo "  Synthetic sample app: http://127.0.0.1:8001/health"
  echo "  Tip: UI on port 8000 only → AUTOPULSE_FRONTEND_MODE=static and open …/ui/ (export is already built at script start)."
  echo "  For Next dev: run \`npm --prefix frontend run dev\` in another shell (this script already exported NEXT_PUBLIC_* for sidecar)."
  if [[ -z "${AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS:-}" ]] && [[ "$(uname -s)" == "Darwin" ]]; then
    _ap_lan_ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
    if [[ -n "$_ap_lan_ip" ]]; then
      export AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS="$_ap_lan_ip"
      echo "AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS=${AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS} (auto en0; override in .env if HMR still blocked)"
    fi
  fi
fi

export AUTOPULSE_EVENT_STORE="duckdb"
export AUTOPULSE_DATA_DIR="${AUTOPULSE_DATA_DIR:-$ROOT_DIR}"
export AUTOPULSE_DUCKDB_PATH="${AUTOPULSE_DUCKDB_PATH:-$AUTOPULSE_DATA_DIR/.autopulse/events.duckdb}"

if [[ -z "${AUTOPULSE_API_KEY:-}" ]]; then
  if [[ -n "${NEXT_PUBLIC_AUTOPULSE_API_KEY:-}" ]]; then
    export AUTOPULSE_API_KEY="$NEXT_PUBLIC_AUTOPULSE_API_KEY"
  else
    echo "error: set AUTOPULSE_API_KEY (or NEXT_PUBLIC_AUTOPULSE_API_KEY) for the synthetic app to ingest into the backend." >&2
    exit 1
  fi
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting backend on :8000…"
uv run uvicorn autopulse_backend.main:app --host 0.0.0.0 --port 8000 --log-level info &
BACKEND_PID=$!

for _ in $(seq 1 120); do
  if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
if ! curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
  echo "error: backend did not become healthy on http://127.0.0.1:8000/health" >&2
  exit 1
fi

export AUTOPULSE_MODE=remote
export AUTOPULSE_INGEST_URL="${AUTOPULSE_INGEST_URL:-http://127.0.0.1:8000/ingest}"

echo "DATABASE_URL=${DATABASE_URL:-<unset>}"
echo "AUTOPULSE_EVENT_STORE=${AUTOPULSE_EVENT_STORE}"
echo "AUTOPULSE_DATA_DIR=${AUTOPULSE_DATA_DIR}"
echo "AUTOPULSE_DUCKDB_PATH=${AUTOPULSE_DUCKDB_PATH}"
echo "AUTOPULSE_FRONTEND_MODE=${AUTOPULSE_FRONTEND_MODE}"
echo "AUTOPULSE_INGEST_URL=${AUTOPULSE_INGEST_URL}"
echo "Starting synthetic app: uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8001 --log-level info"
uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8001 --log-level info
