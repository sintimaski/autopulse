#!/usr/bin/env bash
# Event-plane disaster recovery drill (simulate or real snapshot restore).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${AUTOPULSE_EVENT_PLANE_DRILL_MODE:-simulate}"
SOURCE_SNAPSHOTS_ROOT="${AUTOPULSE_EVENT_PLANE_DRILL_SOURCE_SNAPSHOTS_ROOT:-$ROOT/.autopulse/events-duckdb}"
RESTORE_ROOT="${AUTOPULSE_EVENT_PLANE_DRILL_RESTORE_ROOT:-$ROOT/.autopulse/drill-restore}"

echo "[event-plane-drill] mode=${MODE}"

if [[ "$MODE" == "simulate" ]]; then
  WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/autopulse-event-plane-drill-XXXXXX")"
  SOURCE_SNAPSHOTS_ROOT="${WORKDIR}/source-events-duckdb"
  RESTORE_ROOT="${WORKDIR}/restore-events-duckdb"
  mkdir -p "$SOURCE_SNAPSHOTS_ROOT"
  SNAPSHOT_VERSION="$(date -u +%Y%m%dT%H%M%S%NZ)"
  SNAPSHOT_DIR="${SOURCE_SNAPSHOTS_ROOT}/snapshot-${SNAPSHOT_VERSION}"
  mkdir -p "$SNAPSHOT_DIR"
  export SNAPSHOT_DIR
  uv run python - <<'PY'
from pathlib import Path
import duckdb
import os

snapshot_dir = Path(os.environ["SNAPSHOT_DIR"])
db_path = snapshot_dir / "events.duckdb"
conn = duckdb.connect(str(db_path))
try:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            project_id VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            received_at TIMESTAMP NOT NULL,
            type VARCHAR NOT NULL,
            status_code INTEGER NOT NULL,
            latency_ms DOUBLE NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO events (project_id, timestamp, received_at, type, status_code, latency_ms)
        VALUES ('drill-project', now(), now(), 'request', 200, 12.5)
        """
    )
finally:
    conn.close()
PY
  printf "snapshot_version=%s\n" "$SNAPSHOT_VERSION" > "${SNAPSHOT_DIR}/COMPLETE"
  cat > "${SOURCE_SNAPSHOTS_ROOT}/CURRENT" <<EOF
{"snapshot_version":"${SNAPSHOT_VERSION}","snapshot_dir":"snapshot-${SNAPSHOT_VERSION}","published_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
fi

if [[ ! -f "${SOURCE_SNAPSHOTS_ROOT}/CURRENT" ]]; then
  echo "[event-plane-drill] error: CURRENT pointer missing at ${SOURCE_SNAPSHOTS_ROOT}/CURRENT" >&2
  exit 1
fi

export SOURCE_SNAPSHOTS_ROOT
export RESTORE_ROOT

LATEST_DIR="$(uv run python - <<'PY'
from pathlib import Path
import json
import os
root = Path(os.environ["SOURCE_SNAPSHOTS_ROOT"])
payload = json.loads((root / "CURRENT").read_text(encoding="utf-8"))
snapshot_dir = str(payload.get("snapshot_dir", "")).strip()
if not snapshot_dir:
    raise SystemExit(2)
print(snapshot_dir)
PY
)"

mkdir -p "$RESTORE_ROOT"
cp -f "${SOURCE_SNAPSHOTS_ROOT}/CURRENT" "${RESTORE_ROOT}/CURRENT"
rm -rf "${RESTORE_ROOT:?}/${LATEST_DIR}"
cp -R "${SOURCE_SNAPSHOTS_ROOT}/${LATEST_DIR}" "${RESTORE_ROOT}/${LATEST_DIR}"

uv run python - <<'PY'
from pathlib import Path
from autopulse_backend.services.event_plane_parity import resolve_current_snapshot_duckdb_path
import duckdb
import os

restore_root = Path(os.environ["RESTORE_ROOT"])
db_path = resolve_current_snapshot_duckdb_path(restore_root)
if db_path is None:
    raise SystemExit("restored CURRENT pointer is not readable")
conn = duckdb.connect(str(db_path), read_only=True)
try:
    row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    count = int(row[0] if row else 0)
finally:
    conn.close()
if count < 1:
    raise SystemExit("restored snapshot contains no events")
print(f"restored_events={count}")
PY

echo "[event-plane-drill] success source=${SOURCE_SNAPSHOTS_ROOT} restore=${RESTORE_ROOT} snapshot=${LATEST_DIR}"
