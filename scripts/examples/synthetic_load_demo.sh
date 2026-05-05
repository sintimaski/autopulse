#!/usr/bin/env bash
# Generate weighted traffic against the local synthetic FastAPI fixture (:8001 by default).
# Typical flow: ./scripts/run_synthetic_stack.sh  →  ./scripts/examples/synthetic_load_demo.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"

uv run python -m autopulse.fixtures.synthetic_load \
  --base-url "$BASE_URL" \
  --duration-minutes "${DURATION_MINUTES:-5}" \
  --target-requests "${TARGET_REQUESTS:-200}" \
  --role-mode "${ROLE_MODE:-mixed}" \
  --scenario "${SCENARIO:-realistic}"
