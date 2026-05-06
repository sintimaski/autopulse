from __future__ import annotations

import json
import os
import shutil
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import duckdb

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.metrics import service_metrics
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


@dataclass(frozen=True, slots=True)
class CompactionTickResult:
    runs: tuple[CompactionRunResult, ...]

    @property
    def compacted_shards(self) -> int:
        return sum(run.compacted_shards for run in self.runs)

    @property
    def compacted_rows(self) -> int:
        return sum(run.compacted_rows for run in self.runs)


class EventPlaneCompactor:
    def __init__(
        self,
        *,
        manifest: SqliteShardManifest,
        snapshots_root: str | Path,
        max_shards_per_run: int = 1024,
        max_runs_per_tick: int = 1,
        publish_timeout_seconds: float = 60.0,
        snapshot_retention_count: int = 3,
    ) -> None:
        self._manifest = manifest
        self._snapshots_root = Path(snapshots_root).expanduser().resolve()
        self._snapshots_root.mkdir(parents=True, exist_ok=True)
        self._tmp_root = self._snapshots_root / "_tmp"
        self._tmp_root.mkdir(parents=True, exist_ok=True)
        self._current_pointer = self._snapshots_root / "CURRENT"
        self._max_shards_per_run = max(1, int(max_shards_per_run))
        self._max_runs_per_tick = max(1, int(max_runs_per_tick))
        self._publish_timeout_seconds = max(0.0, float(publish_timeout_seconds))
        self._snapshot_retention_count = max(1, int(snapshot_retention_count))

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
        publish_started = 0.0
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
            publish_started = time.monotonic()
            self._ensure_publish_within_timeout(publish_started, "before_snapshot_rename")
            temp_snapshot_dir.rename(final_snapshot_dir)
            self._ensure_publish_within_timeout(publish_started, "after_snapshot_rename")
            self._publish_current_snapshot_pointer(
                snapshot_dir=final_snapshot_dir,
                snapshot_version=snapshot_version,
            )
            self._ensure_publish_within_timeout(publish_started, "after_pointer_publish")
            self._prune_published_snapshots(current_snapshot=final_snapshot_dir)
            self._ensure_publish_within_timeout(publish_started, "after_snapshot_prune")
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
            if publish_started > 0:
                service_metrics.increment("event_plane.snapshot.publish_failed_total")
            if temp_snapshot_dir.exists():
                shutil.rmtree(temp_snapshot_dir, ignore_errors=True)
            raise

    def compact_tick(self, *, max_runs: int | None = None) -> CompactionTickResult:
        runs: list[CompactionRunResult] = []
        run_budget = int(max_runs) if max_runs is not None else self._max_runs_per_tick
        run_budget = max(1, run_budget)
        for _ in range(run_budget):
            result = self.compact_once()
            if result.compacted_shards <= 0:
                break
            runs.append(result)
        return CompactionTickResult(runs=tuple(runs))

    def list_published_snapshots(self) -> list[Path]:
        published: list[Path] = []
        for candidate in sorted(self._snapshots_root.glob("snapshot-*")):
            if (candidate / "COMPLETE").is_file():
                published.append(candidate)
        return published

    def resolve_current_snapshot_path(self) -> Path | None:
        if not self._current_pointer.is_file():
            return None
        payload = self._read_current_pointer()
        if payload is None:
            return None
        snapshot_dir_name = str(payload.get("snapshot_dir", "")).strip()
        if not snapshot_dir_name:
            return None
        snapshot_path = (self._snapshots_root / snapshot_dir_name).resolve()
        if not snapshot_path.is_dir():
            return None
        if not (snapshot_path / "COMPLETE").is_file():
            return None
        return snapshot_path

    def count_shards_by_state(self) -> dict[ShardManifestState, int]:
        return {
            ShardManifestState.OPEN: len(self._manifest.list_by_state(ShardManifestState.OPEN)),
            ShardManifestState.SEALED: len(self._manifest.list_by_state(ShardManifestState.SEALED)),
            ShardManifestState.COMPACTING: len(
                self._manifest.list_by_state(ShardManifestState.COMPACTING)
            ),
            ShardManifestState.COMPACTED: len(
                self._manifest.list_by_state(ShardManifestState.COMPACTED)
            ),
            ShardManifestState.FAILED: len(self._manifest.list_by_state(ShardManifestState.FAILED)),
        }

    def compaction_lag_seconds(self) -> int:
        now = datetime.now(UTC)
        backlog = self._manifest.list_by_state(
            ShardManifestState.SEALED
        ) + self._manifest.list_by_state(ShardManifestState.COMPACTING)
        if not backlog:
            return 0
        oldest = min(backlog, key=lambda record: record.created_at)
        return max(0, int((now - oldest.created_at).total_seconds()))

    def snapshot_age_seconds(self) -> int:
        payload = self._read_current_pointer()
        if payload is None:
            return 0
        published_raw = payload.get("published_at")
        if not isinstance(published_raw, str) or not published_raw.strip():
            return 0
        published_at = _parse_datetime(published_raw, fallback=datetime.now(UTC))
        return max(0, int((datetime.now(UTC) - published_at).total_seconds()))

    def _reserve_candidates_for_compaction(self) -> list[ShardManifestRecord]:
        sealed = self._manifest.list_by_state(ShardManifestState.SEALED)
        compacting = self._manifest.list_by_state(ShardManifestState.COMPACTING)
        compacting_by_id = {record.shard_id for record in compacting}
        max_new_reservations = max(0, self._max_shards_per_run - len(compacting))
        selected_sealed = self._select_fair_sealed_candidates(
            sealed=sealed,
            limit=max_new_reservations,
        )
        reserved: list[ShardManifestRecord] = []
        for shard in selected_sealed:
            if shard.shard_id in compacting_by_id:
                continue
            updated = self._manifest.transition_state(
                shard_id=shard.shard_id,
                to_state=ShardManifestState.COMPACTING,
            )
            reserved.append(updated)
        reserved.extend(compacting)
        return reserved

    def _select_fair_sealed_candidates(
        self, *, sealed: list[ShardManifestRecord], limit: int
    ) -> list[ShardManifestRecord]:
        if limit <= 0 or not sealed:
            return []
        if len(sealed) <= limit:
            return list(sealed)
        per_project: dict[str, deque[ShardManifestRecord]] = {}
        oldest_by_project: dict[str, datetime] = {}
        for record in sealed:
            queue = per_project.setdefault(record.project_id, deque())
            queue.append(record)
            current_oldest = oldest_by_project.get(record.project_id)
            if current_oldest is None or record.created_at < current_oldest:
                oldest_by_project[record.project_id] = record.created_at
        project_order = sorted(
            per_project.keys(),
            key=lambda project_id: (oldest_by_project[project_id], project_id),
        )
        selected: list[ShardManifestRecord] = []
        while len(selected) < limit and project_order:
            next_round: list[str] = []
            for project_id in project_order:
                queue = per_project[project_id]
                if queue and len(selected) < limit:
                    selected.append(queue.popleft())
                if queue:
                    next_round.append(project_id)
            project_order = next_round
        return selected

    def _publish_current_snapshot_pointer(
        self,
        *,
        snapshot_dir: Path,
        snapshot_version: str,
    ) -> None:
        if not (snapshot_dir / "COMPLETE").is_file():
            raise ValueError(f"cannot publish incomplete snapshot: {snapshot_dir}")
        current = self._read_current_pointer()
        if current is not None:
            current_version = str(current.get("snapshot_version", "")).strip()
            if current_version and current_version > snapshot_version:
                raise ValueError(
                    "snapshot version monotonicity violation: "
                    f"current={current_version} next={snapshot_version}"
                )
        payload: dict[str, object] = {
            "snapshot_version": snapshot_version,
            "snapshot_dir": snapshot_dir.name,
            "published_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        self._write_current_pointer_atomically(payload)

    def _read_current_pointer(self) -> dict[str, object] | None:
        if not self._current_pointer.is_file():
            return None
        try:
            raw = json.loads(self._current_pointer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return None
        if isinstance(raw, dict):
            return cast(dict[str, object], raw)
        return None

    def _write_current_pointer_atomically(self, payload: dict[str, object]) -> None:
        temp_path = self._snapshots_root / f".CURRENT.tmp-{uuid4().hex}"
        try:
            temp_path.write_text(
                json.dumps(payload, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            os.replace(temp_path, self._current_pointer)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def _ensure_publish_within_timeout(self, started_at: float, stage: str) -> None:
        if self._publish_timeout_seconds <= 0:
            return
        elapsed = time.monotonic() - started_at
        if elapsed > self._publish_timeout_seconds:
            raise TimeoutError(
                "event plane compactor publish timeout exceeded "
                f"(stage={stage} elapsed_seconds={elapsed:.3f} "
                f"timeout_seconds={self._publish_timeout_seconds:.3f})"
            )

    def _prune_published_snapshots(self, *, current_snapshot: Path) -> None:
        published = self.list_published_snapshots()
        if len(published) <= self._snapshot_retention_count:
            return
        current_resolved = current_snapshot.resolve()
        deletable = [path for path in published if path.resolve() != current_resolved]
        to_delete_count = max(0, len(published) - self._snapshot_retention_count)
        for old in sorted(deletable)[:to_delete_count]:
            shutil.rmtree(old, ignore_errors=True)

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
                    id BIGINT PRIMARY KEY,
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
            batch_size = 5000
            next_row_id = 1
            for shard in candidates:
                shard_path = Path(shard.shard_path)
                if not shard_path.is_file():
                    raise FileNotFoundError(f"shard file missing: {shard_path}")
                with shard_path.open("r", encoding="utf-8") as shard_file:
                    for line in shard_file:
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
                                next_row_id,
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
                        next_row_id += 1
                        if len(insert_rows) >= batch_size:
                            conn.executemany(
                                """
                                INSERT INTO events (
                                    id, project_id, timestamp, received_at, sdk_version,
                                    type, service_name,
                                    environment, method, path, status_code, latency_ms, payload,
                                    request_id, shard_id
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                insert_rows,
                            )
                            rows_written += len(insert_rows)
                            insert_rows.clear()
            if insert_rows:
                conn.executemany(
                    """
                    INSERT INTO events (
                        id, project_id, timestamp, received_at, sdk_version, type, service_name,
                        environment, method, path, status_code, latency_ms, payload,
                        request_id, shard_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    insert_rows,
                )
                rows_written += len(insert_rows)
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
        max_shards_per_run=resolved.event_plane_compactor_max_shards_per_run,
        max_runs_per_tick=resolved.event_plane_compactor_max_concurrency,
        publish_timeout_seconds=resolved.event_plane_compactor_publish_timeout_seconds,
        snapshot_retention_count=resolved.event_plane_snapshot_retention_count,
    )
