#!/usr/bin/env bash
# Local integration: Lumonox backend (:8000) + synthetic sample app (:8001) + optional Next sidecar.
# Always runs `npm --prefix frontend run build` first (static export → frontend/out/).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Synthetic sample app served on :8001. The Django wrapper
# (scripts/run_synthetic_django_stack.sh) overrides these via the environment
# to swap the FastAPI fixture for the Django one — everything else is identical.
SYNTHETIC_APP_TARGET="${LUMONOX_SYNTHETIC_APP_TARGET:-lumonox.fixtures.synthetic_test_app:app}"
SYNTHETIC_APP_LABEL="${LUMONOX_SYNTHETIC_APP_LABEL:-synthetic FastAPI app}"
SYNTHETIC_APP_HEALTH_PATH="${LUMONOX_SYNTHETIC_APP_HEALTH_PATH:-/health}"
# Extra uvicorn args (the Django fixture entry point is a factory → needs --factory).
SYNTHETIC_APP_UVICORN_ARGS="${LUMONOX_SYNTHETIC_APP_UVICORN_ARGS:-}"

echo "Loading backend/.env…"
set -a
# shellcheck disable=SC1091
source backend/.env
set +a

if [ -f .env.lumonox ]; then
  echo "Loading .env.lumonox (overrides NEXT_PUBLIC_* / ingest key for local UI builds)…"
  set -a
  # shellcheck disable=SC1091
  source .env.lumonox
  set +a
fi

# ``npm run build`` inlines ``NEXT_PUBLIC_*`` at compile time. Force the standalone-backend API
# origin here so stale ``/lumonox`` API bases from older .env files cannot bake into ``frontend/out``.
export NEXT_PUBLIC_LUMONOX_API_BASE_URL="${NEXT_PUBLIC_LUMONOX_API_BASE_URL:-http://127.0.0.1:8000}"
export NEXT_PUBLIC_LUMONOX_DEV_API_ORIGIN="${NEXT_PUBLIC_LUMONOX_DEV_API_ORIGIN:-http://127.0.0.1:8000}"
echo "For frontend build: NEXT_PUBLIC_LUMONOX_API_BASE_URL=${NEXT_PUBLIC_LUMONOX_API_BASE_URL}"

FRONTEND_DIR="$ROOT_DIR/frontend"
if [[ ! -f "$FRONTEND_DIR/node_modules/next/dist/bin/next" ]]; then
  echo "error: frontend dependencies missing (no Next.js CLI)." >&2
  echo "  Run: npm --prefix frontend install" >&2
  exit 1
fi

echo "Building frontend (Next static export → frontend/out/)…"
npm --prefix frontend run build

export LUMONOX_FRONTEND_STATIC_DIR="${LUMONOX_FRONTEND_STATIC_DIR:-$ROOT_DIR/frontend/out}"

FRONTEND_MODE="${LUMONOX_FRONTEND_MODE:-sidecar}"
export LUMONOX_FRONTEND_MODE="$FRONTEND_MODE"

if [[ "$FRONTEND_MODE" == "static" ]]; then
  echo "LUMONOX_FRONTEND_MODE=static: dashboard export is served from the backend under …/lumonox/ui/."
else
  echo "Frontend: Next dev sidecar (LUMONOX_FRONTEND_MODE=$FRONTEND_MODE); static export was built above for the backend mount."
  _ui_mount="${LUMONOX_MOUNT_PREFIX:-/lumonox}"
  echo "  Dashboard UI (Next):  http://localhost:3000/"
  echo "  API (backend):        http://127.0.0.1:8000 (JSON under /dashboard and /lumonox/dashboard; ingest at /ingest and /lumonox/ingest; static UI at http://127.0.0.1:8000${_ui_mount}/ui/ when mounted)"
  echo "  Synthetic sample app: http://127.0.0.1:8001${SYNTHETIC_APP_HEALTH_PATH}"
  echo "  Tip: UI on port 8000 only → LUMONOX_FRONTEND_MODE=static and open …/ui/ (export is already built at script start)."
  echo "  For Next dev: run \`npm --prefix frontend run dev\` in another shell (this script already exported NEXT_PUBLIC_* for sidecar)."
  if [[ -z "${LUMONOX_NEXT_ALLOWED_DEV_ORIGINS:-}" ]] && [[ "$(uname -s)" == "Darwin" ]]; then
    _ap_lan_ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
    if [[ -n "$_ap_lan_ip" ]]; then
      export LUMONOX_NEXT_ALLOWED_DEV_ORIGINS="$_ap_lan_ip"
      echo "LUMONOX_NEXT_ALLOWED_DEV_ORIGINS=${LUMONOX_NEXT_ALLOWED_DEV_ORIGINS} (auto en0; override in .env if HMR still blocked)"
    fi
  fi
fi

export LUMONOX_EVENT_STORE="duckdb"
export LUMONOX_DATA_DIR="${LUMONOX_DATA_DIR:-$ROOT_DIR}"
export LUMONOX_DUCKDB_PATH="${LUMONOX_DUCKDB_PATH:-$LUMONOX_DATA_DIR/.lumonox/events.duckdb}"
# Local synthetic stack is a dev/demo surface — show the bundled widget showcase
# page. Production deployments leave this OFF (see core/config.py).
export LUMONOX_STUDIO_SHOWCASE_DEMO="${LUMONOX_STUDIO_SHOWCASE_DEMO:-true}"

if [[ -z "${LUMONOX_API_KEY:-}" ]]; then
  if [[ -n "${NEXT_PUBLIC_LUMONOX_API_KEY:-}" ]]; then
    export LUMONOX_API_KEY="$NEXT_PUBLIC_LUMONOX_API_KEY"
  else
    echo "error: set LUMONOX_API_KEY (or NEXT_PUBLIC_LUMONOX_API_KEY) for the synthetic app to ingest into the backend." >&2
    exit 1
  fi
fi

BACKEND_LOG=""
cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_LOG:-}" && -f "$BACKEND_LOG" ]]; then
    rm -f "$BACKEND_LOG"
  fi
}
trap cleanup EXIT INT TERM

# Avoid a second uvicorn fighting the same port / DuckDB lock (symptom: /health never succeeds in time).
if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
  echo "error: something already responds on http://127.0.0.1:8000/health." >&2
  echo "  Stop the other process (or free port 8000), then re-run this script." >&2
  exit 1
fi

echo "Starting backend on :8000…"
BACKEND_LOG="$(mktemp)"
uv run uvicorn lumonox_backend.main:app --host 0.0.0.0 --port 8000 --log-level info >>"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Startup can exceed 30s when Alembic runs, DuckDB opens under lock contention
# (see LUMONOX_DUCKDB_CONNECT_RETRIES in event_store), or cold disk — allow ~100s.
for _ in $(seq 1 400); do
  if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "error: backend exited before /health succeeded (check logs below)." >&2
    echo "--- tail ${BACKEND_LOG} ---" >&2
    tail -n 120 "$BACKEND_LOG" >&2 || true
    exit 1
  fi
  sleep 0.25
done
if ! curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
  echo "error: backend did not become healthy on http://127.0.0.1:8000/health within ~100s." >&2
  echo "  Common causes: port 8000 in use, DuckDB file locked by another Lumonox process, or very slow first migration." >&2
  echo "  Tip: ensure no other uvicorn is using this repo's .lumonox/events.duckdb; try lsof on that path." >&2
  echo "--- tail ${BACKEND_LOG} ---" >&2
  tail -n 120 "$BACKEND_LOG" >&2 || true
  exit 1
fi

export LUMONOX_MODE=remote
export LUMONOX_INGEST_URL="${LUMONOX_INGEST_URL:-http://127.0.0.1:8000/ingest}"

echo "DATABASE_URL=${DATABASE_URL:-<unset>}"
echo "LUMONOX_EVENT_STORE=${LUMONOX_EVENT_STORE}"
echo "LUMONOX_DATA_DIR=${LUMONOX_DATA_DIR}"
echo "LUMONOX_DUCKDB_PATH=${LUMONOX_DUCKDB_PATH}"
echo "LUMONOX_FRONTEND_MODE=${LUMONOX_FRONTEND_MODE}"
echo "LUMONOX_INGEST_URL=${LUMONOX_INGEST_URL}"
_backend_ui_url=""
if curl -sf "http://127.0.0.1:8000/lumonox/ui/" >/dev/null 2>&1; then
  _backend_ui_url="http://127.0.0.1:8000/lumonox/ui/"
elif curl -sf "http://127.0.0.1:8000/ui/" >/dev/null 2>&1; then
  _backend_ui_url="http://127.0.0.1:8000/ui/"
fi
if [[ -n "$_backend_ui_url" ]]; then
  echo "Dashboard UI (backend static): ${_backend_ui_url}"
else
  echo "Dashboard UI (backend static): not mounted (expected in sidecar-only setups)."
  echo "  If you open /lumonox/ui/ on :8000 in this state, backend access logs will show 404."
fi
echo "Starting ${SYNTHETIC_APP_LABEL}: uv run uvicorn ${SYNTHETIC_APP_TARGET} ${SYNTHETIC_APP_UVICORN_ARGS} --host 0.0.0.0 --port 8001 --log-level info"
# shellcheck disable=SC2086  # SYNTHETIC_APP_UVICORN_ARGS must word-split (e.g. "--factory").
uv run uvicorn "${SYNTHETIC_APP_TARGET}" ${SYNTHETIC_APP_UVICORN_ARGS} --host 0.0.0.0 --port 8001 --log-level info
