from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.services.event_plane_manifest import (
    ShardManifestRecord,
    ShardManifestState,
    SqliteShardManifest,
)


def _utc_now_compact_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _parse_datetime(value: object, *, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return fallback


@dataclass(frozen=True, slots=True)
class CompactionRunResult:
    snapshot_version: str | None
    compacted_shards: int
    compacted_rows: int
    published_snapshot_path: Path | None


class EventPlaneCompactor:
    def __init__(
        self,
        *,
        manifest: SqliteShardManifest,
        snapshots_root: str | Path,
    ) -> None:
        self._manifest = manifest
        self._snapshots_root = Path(snapshots_root).expanduser().resolve()
        self._snapshots_root.mkdir(parents=True, exist_ok=True)
        self._tmp_root = self._snapshots_root / "_tmp"
        self._tmp_root.mkdir(parents=True, exist_ok=True)

    @property
    def snapshots_root(self) -> Path:
        return self._snapshots_root

    def compact_once(self) -> CompactionRunResult:
        candidates = self._reserve_candidates_for_compaction()
        if not candidates:
            return CompactionRunResult(
                snapshot_version=None,
                compacted_shards=0,
                compacted_rows=0,
                published_snapshot_path=None,
            )
        snapshot_version = _utc_now_compact_id()
        temp_snapshot_dir = self._tmp_root / f"snapshot-{snapshot_version}-{uuid4().hex}"
        final_snapshot_dir = self._snapshots_root / f"snapshot-{snapshot_version}"
        compacted_rows = 0
        try:
            temp_snapshot_dir.mkdir(parents=True, exist_ok=False)
            compacted_rows = self._build_snapshot(
                target_dir=temp_snapshot_dir,
                candidates=candidates,
                snapshot_version=snapshot_version,
            )
            (temp_snapshot_dir / "COMPLETE").write_text(
                f"snapshot_version={snapshot_version}\n",
                encoding="utf-8",
            )
            temp_snapshot_dir.rename(final_snapshot_dir)
            for shard in candidates:
                self._manifest.transition_state(
                    shard_id=shard.shard_id,
                    to_state=ShardManifestState.COMPACTED,
                )
            return CompactionRunResult(
                snapshot_version=snapshot_version,
                compacted_shards=len(candidates),
                compacted_rows=compacted_rows,
                published_snapshot_path=final_snapshot_dir,
            )
        except Exception:
            # Keep shards as "compacting" so retries can resume safely.
            if temp_snapshot_dir.exists():
                shutil.rmtree(temp_snapshot_dir, ignore_errors=True)
            raise

    def list_published_snapshots(self) -> list[Path]:
        published: list[Path] = []
        for candidate in sorted(self._snapshots_root.glob("snapshot-*")):
            if (candidate / "COMPLETE").is_file():
                published.append(candidate)
        return published

    def _reserve_candidates_for_compaction(self) -> list[ShardManifestRecord]:
        sealed = self._manifest.list_by_state(ShardManifestState.SEALED)
        compacting = self._manifest.list_by_state(ShardManifestState.COMPACTING)
        reserved: list[ShardManifestRecord] = []
        for shard in sealed:
            updated = self._manifest.transition_state(
                shard_id=shard.shard_id,
                to_state=ShardManifestState.COMPACTING,
            )
            reserved.append(updated)
        reserved.extend(compacting)
        return reserved

    def _build_snapshot(
        self,
        *,
        target_dir: Path,
        candidates: list[ShardManifestRecord],
        snapshot_version: str,
    ) -> int:
        db_path = target_dir / "events.duckdb"
        conn = duckdb.connect(str(db_path))
        rows_written = 0
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    project_id VARCHAR NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    received_at TIMESTAMP NOT NULL,
                    sdk_version VARCHAR NOT NULL,
                    type VARCHAR NOT NULL,
                    service_name VARCHAR NOT NULL,
                    environment VARCHAR NOT NULL,
                    method VARCHAR NOT NULL,
                    path VARCHAR NOT NULL,
                    status_code INTEGER NOT NULL,
                    latency_ms DOUBLE NOT NULL,
                    payload JSON NOT NULL,
                    request_id VARCHAR,
                    shard_id VARCHAR NOT NULL
                )
                """
            )
            insert_rows: list[tuple[object, ...]] = []
            for shard in candidates:
                shard_path = Path(shard.shard_path)
                if not shard_path.is_file():
                    raise FileNotFoundError(f"shard file missing: {shard_path}")
                for line in shard_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    parsed = json.loads(line)
                    received_at = _parse_datetime(
                        parsed.get("received_at"), fallback=shard.created_at
                    )
                    event_ts = _parse_datetime(parsed.get("timestamp"), fallback=received_at)
                    payload = parsed.get("payload")
                    payload_json = payload if isinstance(payload, dict) else {}
                    insert_rows.append(
                        (
                            str(parsed.get("project_id") or shard.project_id),
                            event_ts.replace(tzinfo=None),
                            received_at.replace(tzinfo=None),
                            str(parsed.get("sdk_version") or "unknown"),
                            str(parsed.get("type") or "request"),
                            str(parsed.get("service_name") or "unknown"),
                            str(parsed.get("environment") or "unknown"),
                            str(parsed.get("method") or "GET"),
                            str(parsed.get("path") or "/unknown"),
                            int(parsed.get("status_code") or 0),
                            float(parsed.get("latency_ms") or 0.0),
                            json.dumps(payload_json),
                            (
                                str(parsed.get("request_id"))
                                if parsed.get("request_id") is not None
                                else None
                            ),
                            shard.shard_id,
                        )
                    )
            if insert_rows:
                conn.executemany(
                    """
                    INSERT INTO events (
                        project_id, timestamp, received_at, sdk_version, type, service_name,
                        environment, method, path, status_code, latency_ms, payload,
                        request_id, shard_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    insert_rows,
                )
                rows_written = len(insert_rows)
            (target_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "snapshot_version": snapshot_version,
                        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "shard_ids": [s.shard_id for s in candidates],
                        "rows_written": rows_written,
                    },
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
        finally:
            conn.close()
        return rows_written


def make_event_plane_compactor(
    *,
    settings: Settings | None = None,
    manifest: SqliteShardManifest | None = None,
) -> EventPlaneCompactor:
    resolved = settings if settings is not None else get_settings()
    resolved_manifest = manifest
    if resolved_manifest is None:
        resolved_manifest = SqliteShardManifest(
            Path(resolved.event_plane_shards_path).parent / "events-index" / "manifest.sqlite"
        )
    return EventPlaneCompactor(
        manifest=resolved_manifest,
        snapshots_root=resolved.event_plane_snapshots_path,
    )
