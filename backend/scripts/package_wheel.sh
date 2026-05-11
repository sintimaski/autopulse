#!/usr/bin/env bash
# Build ``frontend/out`` then ``uv build backend`` so the wheel bundles the dashboard export
# under ``lumonox_backend/dashboard_static`` (mounts at ``/lumonox/ui`` when enabled).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f frontend/package.json ]]; then
  echo "error: run from repo with frontend/ directory (expected ${ROOT}/frontend/package.json)" >&2
  exit 1
fi

# Match ``scripts/run_synthetic_stack.sh`` – ``NEXT_PUBLIC_*`` is baked into the export.
export NEXT_PUBLIC_LUMONOX_API_BASE_URL="${NEXT_PUBLIC_LUMONOX_API_BASE_URL:-http://127.0.0.1:8000}"
export NEXT_PUBLIC_LUMONOX_DEV_API_ORIGIN="${NEXT_PUBLIC_LUMONOX_DEV_API_ORIGIN:-http://127.0.0.1:8000}"

npm --prefix frontend run build

out_dir="${1:-dist/pypi-backend}"
mkdir -p "$out_dir"
uv build backend -o "$out_dir"

echo "Built lumonox wheel + sdist → ${ROOT}/${out_dir}"
