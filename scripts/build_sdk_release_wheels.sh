#!/usr/bin/env bash
# Build ``autopulse-sdk`` + ``autopulse-backend`` wheels for offline / pre-PyPI installs.
# Remote ingest needs the backend running separately; ``pip install autopulse-sdk`` is SDK-only (import name ``autopulse``).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/dist/wheels}"
mkdir -p "$OUT"
cd "$ROOT"
uv build --package autopulse-backend --wheel -o "$OUT"
uv build --package autopulse-sdk --wheel -o "$OUT"
echo "Wheels in $OUT:"
ls -1 "$OUT"/*.whl
echo
echo "Install both wheels (backend + SDK for the same checkout or offline install):"
echo "  pip install \"$OUT\"/autopulse_backend-*.whl \"$OUT\"/autopulse_sdk-*.whl"
echo "Parquet object storage with s3:// also needs boto3 (optional extra on the backend wheel):"
echo "  pip install \"$OUT\"/autopulse_backend-*.whl[parquet-s3] \"$OUT\"/autopulse_sdk-*.whl"
