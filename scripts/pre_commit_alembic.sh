#!/usr/bin/env bash
# Pre-commit: Alembic graph + offline SQL + SQLite apply smoke (no server required).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/backend"

heads_out="$(uv run alembic heads 2>/dev/null | grep -E '\S' || true)"
n_heads="$(printf '%s\n' "$heads_out" | grep -c . || true)"
if [[ "$n_heads" -ne 1 ]]; then
  echo "alembic: expected exactly one head; got:" >&2
  printf '%s\n' "$heads_out" >&2
  exit 1
fi

# Offline: ensure every revision renders for the configured dialect (Postgres in alembic.ini).
uv run alembic upgrade head --sql >/dev/null

# Online smoke: apply full chain on a throwaway SQLite file (catches dialect-only breakage).
# Relative DATABASE_URL paths are anchored to LUMONOX_DATA_DIR / monorepo root (see
# normalize_database_url), not backend cwd — rm the resolved repo-root file, not backend/.
pre_db="${ROOT}/.pre-commit-alembic.db"
rm -f "$pre_db" "${pre_db}-wal" "${pre_db}-shm"
(
  export LUMONOX_DATA_DIR="$ROOT"
  export DATABASE_URL="sqlite+aiosqlite:///./.pre-commit-alembic.db"
  uv run alembic upgrade head
)
