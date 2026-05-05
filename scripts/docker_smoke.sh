#!/usr/bin/env bash
# Build the official image and verify /health + /ready (production-style env).
# Requires a running Docker daemon (Docker Desktop, colima, etc.).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
IMAGE="${AUTOPULSE_DOCKER_IMAGE:-autopulse:local}"
PORT="${AUTOPULSE_DOCKER_SMOKE_PORT:-8000}"

if ! docker info >/dev/null 2>&1; then
  echo "error: docker daemon not reachable (start Docker Desktop or similar)" >&2
  exit 1
fi

echo "Building ${IMAGE}..."
docker build -t "$IMAGE" "$ROOT"

CID="$(
  docker run -d \
    -p "${PORT}:8000" \
    -e AUTOPULSE_ENV=production \
    -e DASHBOARD_AUTH_ENABLED=true \
    -e DASHBOARD_AUTH_ALLOWED_EMAIL=smoke@example.com \
    -e DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS=true \
    -e INTERNAL_METRICS_BEARER_TOKEN=smoke-test-token \
    "$IMAGE"
)"
cleanup() {
  docker rm -f "$CID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

base="http://127.0.0.1:${PORT}"
echo "Waiting for ${base}/health ..."
for _ in $(seq 1 90); do
  if curl -sf "${base}/health" | grep -q '"status"'; then
    break
  fi
  sleep 1
done
if ! curl -sf "${base}/health" | grep -q '"status"'; then
  echo "timeout waiting for /health" >&2
  docker logs "$CID" >&2 || true
  exit 1
fi
echo "GET /health OK"

if ! curl -sf "${base}/ready" | grep -q '"status":"ready"'; then
  echo "GET /ready failed" >&2
  docker logs "$CID" >&2 || true
  exit 1
fi
echo "GET /ready OK"
echo "Docker smoke passed."
