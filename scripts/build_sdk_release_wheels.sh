#!/usr/bin/env bash
# Build ``lumonox-sdk`` + ``lumonox-api`` wheels for offline / pre-PyPI installs.
# Remote ingest needs the API process separately; ``pip install lumonox-sdk`` is SDK-only (import package ``lumonox``).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/dist/wheels}"
mkdir -p "$OUT"
cd "$ROOT"
uv build --package lumonox-api --wheel -o "$OUT"
uv build --package lumonox-sdk --wheel -o "$OUT"
echo "Wheels in $OUT:"
ls -1 "$OUT"/*.whl
echo
echo "Install both wheels (API + bundled UI + SDK for the same checkout or offline install):"
echo "  pip install \"$OUT\"/lumonox_api-*.whl \"$OUT\"/lumonox_sdk-*.whl"
echo "Parquet object storage with s3:// also needs boto3 (optional extra on the API wheel):"
echo "  pip install \"$OUT\"/lumonox_api-*.whl[parquet-s3] \"$OUT\"/lumonox_sdk-*.whl"
