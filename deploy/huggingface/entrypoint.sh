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

# LUMONOX_FRONTEND_STATIC_DIR is set in the Dockerfile to the freshly-built dashboard
# from the multi-stage build (/opt/lumonox-dashboard). Log it for visibility.
echo "[entrypoint] dashboard static export: ${LUMONOX_FRONTEND_STATIC_DIR:-<unset>}"

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
