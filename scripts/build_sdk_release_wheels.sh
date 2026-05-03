#!/usr/bin/env bash
# Build ``autopulse`` + ``autopulse-backend`` wheels for offline / pre-PyPI installs.
# Embedded mode needs both; ``pip install autopulse`` alone cannot pull the backend until it is published.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/dist/wheels}"
mkdir -p "$OUT"
cd "$ROOT"
uv build --package autopulse-backend --wheel -o "$OUT"
uv build --package autopulse --wheel -o "$OUT"
echo "Wheels in $OUT:"
ls -1 "$OUT"/*.whl
echo
echo "Install embedded stack (backend first, then SDK):"
echo "  pip install \"$OUT\"/autopulse_backend-*.whl \"$OUT\"/autopulse-*.whl"
