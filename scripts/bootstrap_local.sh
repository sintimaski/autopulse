#!/usr/bin/env bash
# Bootstrap local Lumonox development dependencies and env files.
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

if [[ ! -f .env.lumonox ]]; then
  echo "Creating .env.lumonox from .env.lumonox.example..."
  cp .env.lumonox.example .env.lumonox
else
  echo ".env.lumonox already exists; keeping current file."
fi

echo "Bootstrap complete."
echo "Next: set LUMONOX_API_KEY in backend/.env or .env.lumonox, then run:"
echo "  ./scripts/run_synthetic_stack.sh"
