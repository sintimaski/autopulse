from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class ShardManifestState(StrEnum):
    OPEN = "open"
    SEALED = "sealed"
    COMPACTING = "compacting"
    COMPACTED = "compacted"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[ShardManifestState, frozenset[ShardManifestState]] = {
    ShardManifestState.OPEN: frozenset({ShardManifestState.SEALED, ShardManifestState.FAILED}),
    ShardManifestState.SEALED: frozenset(
        {ShardManifestState.COMPACTING, ShardManifestState.FAILED}
    ),
    ShardManifestState.COMPACTING: frozenset(
        {ShardManifestState.COMPACTED, ShardManifestState.FAILED}
    ),
    ShardManifestState.COMPACTED: frozenset(),
    ShardManifestState.FAILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class ShardManifestRecord:
    shard_id: str
    project_id: str
    shard_path: str
    state: ShardManifestState
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None


class SqliteShardManifest:
    def __init__(self, manifest_path: str | Path) -> None:
        self._path = Path(manifest_path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        self._ensure_schema()

    @property
    def manifest_path(self) -> Path:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def register_open_shard(
        self, *, shard_id: str, project_id: str, shard_path: str
    ) -> ShardManifestRecord:
        now = _utc_now_iso()
        with self._lock:
            existing = self._fetch_record_locked(shard_id)
            if existing is not None:
                if (
                    existing.project_id != project_id
                    or existing.shard_path != shard_path
                    or existing.state != ShardManifestState.OPEN
                ):
                    raise ValueError(
                        "register_open_shard conflict for existing shard_id "
                        "with mismatched fields/state"
                    )
                return existing
            self._conn.execute(
                """
                INSERT INTO event_plane_shard_manifest (
                    shard_id,
                    project_id,
                    shard_path,
                    state,
                    created_at,
                    updated_at,
                    last_error
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (shard_id, project_id, shard_path, ShardManifestState.OPEN.value, now, now),
            )
            self._conn.commit()
            created = self._fetch_record_locked(shard_id)
            assert created is not None
            return created

    def transition_state(
        self,
        *,
        shard_id: str,
        to_state: ShardManifestState,
        last_error: str | None = None,
    ) -> ShardManifestRecord:
        with self._lock:
            record = self._fetch_record_locked(shard_id)
            if record is None:
                raise KeyError(f"shard_id not found: {shard_id}")
            if record.state == to_state:
                return record
            allowed = _ALLOWED_TRANSITIONS[record.state]
            if to_state not in allowed:
                raise ValueError(
                    f"Invalid shard manifest transition: {record.state.value} -> {to_state.value}"
                )
            now = _utc_now_iso()
            self._conn.execute(
                """
                UPDATE event_plane_shard_manifest
                SET state = ?, updated_at = ?, last_error = ?
                WHERE shard_id = ?
                """,
                (
                    to_state.value,
                    now,
                    last_error if to_state == ShardManifestState.FAILED else None,
                    shard_id,
                ),
            )
            self._conn.commit()
            updated = self._fetch_record_locked(shard_id)
            assert updated is not None
            return updated

    def get_shard(self, shard_id: str) -> ShardManifestRecord | None:
        with self._lock:
            return self._fetch_record_locked(shard_id)

    def list_by_state(self, state: ShardManifestState) -> list[ShardManifestRecord]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT shard_id, project_id, shard_path, state, created_at, updated_at, last_error
                FROM event_plane_shard_manifest
                WHERE state = ?
                ORDER BY created_at ASC, shard_id ASC
                """,
                (state.value,),
            )
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    def _ensure_schema(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_plane_shard_manifest (
                shard_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                shard_path TEXT NOT NULL,
                state TEXT NOT NULL CHECK (
                    state IN ('open', 'sealed', 'compacting', 'compacted', 'failed')
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_event_plane_shard_manifest_state_created
            ON event_plane_shard_manifest(state, created_at)
            """
        )
        self._conn.commit()

    def _fetch_record_locked(self, shard_id: str) -> ShardManifestRecord | None:
        cursor = self._conn.execute(
            """
            SELECT shard_id, project_id, shard_path, state, created_at, updated_at, last_error
            FROM event_plane_shard_manifest
            WHERE shard_id = ?
            """,
            (shard_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def _row_to_record(self, row: sqlite3.Row) -> ShardManifestRecord:
        return ShardManifestRecord(
            shard_id=str(row["shard_id"]),
            project_id=str(row["project_id"]),
            shard_path=str(row["shard_path"]),
            state=ShardManifestState(str(row["state"])),
            created_at=_parse_iso_utc(str(row["created_at"])),
            updated_at=_parse_iso_utc(str(row["updated_at"])),
            last_error=(str(row["last_error"]) if row["last_error"] is not None else None),
        )
