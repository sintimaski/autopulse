#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Building frontend..."
npm --prefix frontend run build

echo "Loading backend/.env and starting synthetic app..."
set -a
# shellcheck disable=SC1091
source backend/.env
set +a

echo "DATABASE_URL=${DATABASE_URL:-<unset>}"
echo "Starting: uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8010 --log-level info"
exec uv run uvicorn autopulse.fixtures.synthetic_test_app:app --host 0.0.0.0 --port 8010 --log-level info
