#!/usr/bin/env bash
# Bootstrap local AutoPulse development dependencies and env files.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm is required. Install Node.js LTS first." >&2
  exit 1
fi

echo "Installing Python dependencies (including dev group)..."
uv sync --group dev

echo "Installing frontend dependencies..."
npm --prefix frontend install

if [[ ! -f backend/.env ]]; then
  echo "Creating backend/.env from backend/.env.example..."
  cp backend/.env.example backend/.env
else
  echo "backend/.env already exists; keeping current file."
fi

if [[ ! -f .env.autopulse ]]; then
  echo "Creating .env.autopulse from .env.autopulse.example..."
  cp .env.autopulse.example .env.autopulse
else
  echo ".env.autopulse already exists; keeping current file."
fi

echo "Bootstrap complete."
echo "Next: set AUTOPULSE_API_KEY in backend/.env or .env.autopulse, then run:"
echo "  ./scripts/run_synthetic_stack.sh"
