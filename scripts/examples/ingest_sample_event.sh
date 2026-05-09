#!/usr/bin/env bash
# POST one sample Lumonox ingest event (for manual smoke checks).
#
# Usage:
#   export INGEST_KEY='ap_live_…'
#   ./scripts/examples/ingest_sample_event.sh
#
# Optional:
#   INGEST_URL=https://your-host/lumonox/ingest ./scripts/examples/ingest_sample_event.sh
set -euo pipefail

INGEST_URL="${INGEST_URL:-http://127.0.0.1:8000/ingest}"
INGEST_KEY="${INGEST_KEY:-}"
if [[ -z "$INGEST_KEY" ]]; then
  echo "error: set INGEST_KEY (project ingest/API key)." >&2
  exit 1
fi

curl -sS -X POST "$INGEST_URL" \
  -H "Authorization: Bearer ${INGEST_KEY}" \
  -H 'content-type: application/json' \
  --data-binary @- <<'EOF'
{"events":[{"type":"request","timestamp":"2026-01-01T00:00:00Z","service_name":"checkout","environment":"dev","method":"GET","path":"/orders/1","status_code":200,"latency_ms":42}]}
EOF
