#!/usr/bin/env bash
# Lumonox demo orchestration for Hugging Face Spaces.
#
#   1. bootstrap the demo tenant (organization / project / dashboard user + ingest key)
#      and run DB migrations — SQLite-only, before the API process starts
#   2. start the Lumonox API (it serves the dashboard UI on the same origin)
#   3. backfill synthetic history so the dashboard is populated on first load
#   4. keep a light live traffic trickle running so the demo stays in motion
#
# The Spaces free-tier filesystem is ephemeral, so every cold start re-seeds from
# scratch. That is intentional — the demo self-cleans on each restart.
set -euo pipefail

PORT="${LUMONOX_DEMO_PORT:-8000}"

# Defensive pin for the dashboard static export. lumonox 0.3.1+ auto-discovers the
# bundled export (lumonox_backend/dashboard_static/) on its own; on 0.2.12–0.3.0 the
# wheel's discovery looked one directory too deep and /lumonox/ui/ silently 404'd.
# LUMONOX_FRONTEND_STATIC_DIR is the highest-priority lookup path, so setting it keeps
# the demo correct regardless of which pinned wheel is in use.
if [[ -z "${LUMONOX_FRONTEND_STATIC_DIR:-}" ]]; then
  STATIC_DIR="$(python -c 'import lumonox_backend, pathlib, sys; p = pathlib.Path(lumonox_backend.__file__).parent / "dashboard_static"; sys.stdout.write(str(p) if (p / "index.html").is_file() else "")')"
  if [[ -n "${STATIC_DIR}" ]]; then
    export LUMONOX_FRONTEND_STATIC_DIR="${STATIC_DIR}"
    echo "[entrypoint] dashboard static export: ${STATIC_DIR}"
  else
    echo "[entrypoint] WARNING: bundled dashboard_static not found in the lumonox wheel" >&2
  fi
fi

echo "[entrypoint] bootstrapping demo tenant + running migrations…"
python seed_demo.py --bootstrap

echo "[entrypoint] starting Lumonox API on :${PORT}…"
# --proxy-headers + --forwarded-allow-ips lets request.url.scheme resolve to https
# behind the Spaces TLS proxy, so magic-link URLs and the session cookie are correct.
uvicorn lumonox_backend.main:app \
  --host 0.0.0.0 --port "${PORT}" \
  --proxy-headers --forwarded-allow-ips='*' \
  --log-level info &
API_PID=$!

LIVE_PID=""
cleanup() {
  [[ -n "${LIVE_PID}" ]] && kill "${LIVE_PID}" 2>/dev/null || true
  kill "${API_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# seed_demo.py --backfill waits for /health itself before posting; on failure we keep
# the API up anyway so the dashboard still loads (just without seeded history).
echo "[entrypoint] backfilling synthetic history…"
if ! python seed_demo.py --backfill; then
  echo "[entrypoint] backfill failed — continuing without seeded history" >&2
fi

echo "[entrypoint] starting live traffic trickle…"
python seed_demo.py --live &
LIVE_PID=$!

# Keep the container tied to the API process: if uvicorn exits, the container exits.
wait "${API_PID}"
