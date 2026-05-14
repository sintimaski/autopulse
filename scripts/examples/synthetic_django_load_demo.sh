#!/usr/bin/env bash
# Generate simple weighted traffic against the synthetic Django fixture (:8001 by default).
#
# The Django fixture is intentionally a minimum-viable app (3 routes: /health/,
# /users/<id>/, /boom/), so this is a plain curl loop rather than the
# FastAPI-route-tuned `lumonox.fixtures.synthetic_load` generator.
#
# Typical flow:
#   ./scripts/run_synthetic_django_stack.sh
#   ./scripts/examples/synthetic_django_load_demo.sh
#
# Env vars: BASE_URL, TARGET_REQUESTS, SLEEP_SECONDS.
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
BASE_URL="${BASE_URL%/}"
TARGET_REQUESTS="${TARGET_REQUESTS:-200}"
SLEEP_SECONDS="${SLEEP_SECONDS:-0.2}"

echo "synthetic_django_load: starting"
echo "- base_url: ${BASE_URL}"
echo "- target_requests: ${TARGET_REQUESTS}"
echo "- sleep_seconds: ${SLEEP_SECONDS}"

ok=0
non_2xx=0
for ((i = 1; i <= TARGET_REQUESTS; i++)); do
  # Weighting: ~50% health, ~40% parameterized user reads, ~10% the /boom/
  # route so request + error events both show up on the dashboard.
  roll=$((RANDOM % 10))
  if ((roll < 5)); then
    path="/health/"
  elif ((roll < 9)); then
    path="/users/$((RANDOM % 1000))/"
  else
    path="/boom/"
  fi

  request_id="djload-$(printf '%05d' "$i")"
  code="$(curl -s -o /dev/null -w '%{http_code}' \
    -H "X-Request-ID: ${request_id}" \
    "${BASE_URL}${path}")" || code="000"

  if [[ "$code" =~ ^2 ]]; then
    ok=$((ok + 1))
  else
    non_2xx=$((non_2xx + 1))
  fi

  sleep "$SLEEP_SECONDS"
done

echo "synthetic_django_load: complete"
echo "- ok_2xx: ${ok}"
echo "- non_2xx_or_error: ${non_2xx}"
