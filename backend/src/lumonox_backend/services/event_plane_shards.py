from __future__ import annotations

import json
import os
import re
import shutil
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import UUID, uuid4

from lumonox_backend.core.config import Settings, get_settings
from lumonox_backend.metrics import service_metrics
from lumonox_backend.services.event_plane_manifest import (
    ShardManifestState,
    SqliteShardManifest,
)


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _sanitize_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or "unknown"


class ShardDurabilityMode(StrEnum):
    ALWAYS = "always"
    INTERVAL = "interval"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ShardWriteResult:
    shard_path: Path
    shard_id: str
    records_appended: int
    bytes_appended: int
    rotated: bool
    fsync_performed: bool
    sealed_shard_ids: tuple[str, ...] = ()


class EventPlaneBackpressureError(RuntimeError):
    pass


@dataclass(slots=True)
class _OpenShard:
    shard_id: str
    project_segment: str
    time_bucket: str
    path: Path
    fd: int
    opened_at_monotonic: float
    bytes_written: int
    rows_written: int
    last_fsync_monotonic: float


class EventShardWriter(Protocol):
    def append_rows(
        self,
        *,
        project_id: str,
        received_at: datetime,
        rows: Sequence[Mapping[str, Any]],
    ) -> ShardWriteResult: ...

    def close(self) -> None: ...


class LocalAppendOnlyShardWriter:
    def __init__(
        self,
        *,
        root_dir: str | Path,
        max_shard_bytes: int,
        max_shard_age_seconds: int,
        durability_mode: ShardDurabilityMode = ShardDurabilityMode.ALWAYS,
        durability_interval_seconds: float = 1.0,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._root_dir = Path(root_dir).expanduser().resolve()
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._max_shard_bytes = max(1, int(max_shard_bytes))
        self._max_shard_age_seconds = max(1, int(max_shard_age_seconds))
        self._durability_mode = durability_mode
        self._durability_interval_seconds = max(0.0, float(durability_interval_seconds))
        self._monotonic = monotonic or time.monotonic
        self._lock = Lock()
        self._open_shard: _OpenShard | None = None

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def close(self) -> None:
        with self._lock:
            self._close_open_shard()

    def close_and_seal(self) -> tuple[str, ...]:
        with self._lock:
            sealed = self._close_open_shard()
            if sealed is None:
                return ()
            return (sealed.shard_id,)

    def append_rows(
        self,
        *,
        project_id: str,
        received_at: datetime,
        rows: Sequence[Mapping[str, Any]],
    ) -> ShardWriteResult:
        if not rows:
            raise ValueError("append_rows requires at least one row")
        payload = self._serialize_rows(rows)
        project_segment = _sanitize_segment(project_id)
        received_utc = (
            received_at.replace(tzinfo=UTC)
            if received_at.tzinfo is None
            else received_at.astimezone(UTC)
        )
        bucket = received_utc.strftime("%Y/%m/%d/%H")
        with self._lock:
            rotated, sealed_shard_ids = self._ensure_open_shard_for_append(
                project_segment=project_segment,
                time_bucket=bucket,
                incoming_bytes=len(payload),
            )
            assert self._open_shard is not None
            shard = self._open_shard
            written = os.write(shard.fd, payload)
            if written != len(payload):
                raise OSError(f"short write: expected {len(payload)} bytes, wrote {written} bytes")
            shard.bytes_written += written
            shard.rows_written += len(rows)
            fsync_performed = self._maybe_fsync(shard, force=False)
            return ShardWriteResult(
                shard_path=shard.path,
                shard_id=shard.shard_id,
                records_appended=len(rows),
                bytes_appended=written,
                rotated=rotated,
                fsync_performed=fsync_performed,
                sealed_shard_ids=sealed_shard_ids,
            )

    def _serialize_rows(self, rows: Sequence[Mapping[str, Any]]) -> bytes:
        encoded_rows = [
            json.dumps(dict(row), separators=(",", ":"), default=_json_default) + "\n"
            for row in rows
        ]
        return "".join(encoded_rows).encode("utf-8")

    def _ensure_open_shard_for_append(
        self,
        *,
        project_segment: str,
        time_bucket: str,
        incoming_bytes: int,
    ) -> tuple[bool, tuple[str, ...]]:
        now = self._monotonic()
        current = self._open_shard
        should_rotate = False
        if current is None:
            should_rotate = True
        else:
            age_seconds = now - current.opened_at_monotonic
            should_rotate = (
                current.project_segment != project_segment
                or current.time_bucket != time_bucket
                or current.bytes_written + incoming_bytes > self._max_shard_bytes
                or age_seconds >= self._max_shard_age_seconds
            )
        if should_rotate:
            sealed = self._close_open_shard()
            self._open_shard = self._create_open_shard(
                project_segment=project_segment,
                time_bucket=time_bucket,
                now=now,
            )
            if sealed is None:
                return True, ()
            return True, (sealed.shard_id,)
        return False, ()

    def _create_open_shard(
        self, *, project_segment: str, time_bucket: str, now: float
    ) -> _OpenShard:
        shard_dir = self._root_dir / project_segment / time_bucket
        shard_dir.mkdir(parents=True, exist_ok=True)
        shard_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex}"
        shard_name = f"shard-{shard_id}.jsonl"
        shard_path = shard_dir / shard_name
        fd = os.open(shard_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640)
        existing_size = int(os.fstat(fd).st_size)
        return _OpenShard(
            shard_id=shard_id,
            project_segment=project_segment,
            time_bucket=time_bucket,
            path=shard_path,
            fd=fd,
            opened_at_monotonic=now,
            bytes_written=existing_size,
            rows_written=0,
            last_fsync_monotonic=now,
        )

    def _close_open_shard(self) -> _OpenShard | None:
        shard = self._open_shard
        if shard is None:
            return None
        try:
            self._maybe_fsync(shard, force=True)
        finally:
            try:
                os.close(shard.fd)
            finally:
                self._open_shard = None
        return shard

    def _maybe_fsync(self, shard: _OpenShard, *, force: bool) -> bool:
        if self._durability_mode == ShardDurabilityMode.NONE and not force:
            return False
        now = self._monotonic()
        should_fsync = force or self._durability_mode == ShardDurabilityMode.ALWAYS
        if not should_fsync and self._durability_mode == ShardDurabilityMode.INTERVAL:
            should_fsync = (now - shard.last_fsync_monotonic) >= self._durability_interval_seconds
        if not should_fsync:
            return False
        os.fsync(shard.fd)
        shard.last_fsync_monotonic = now
        return True


_event_plane_shard_writer: LocalAppendOnlyShardWriter | None = None
_event_plane_shard_writer_lock = Lock()
_event_plane_manifest: SqliteShardManifest | None = None
_event_plane_manifest_lock = Lock()
_event_plane_backpressure_probe_lock = Lock()
_event_plane_backpressure_probe_cache: dict[str, tuple[float, int]] = {}
_EVENT_PLANE_BACKPRESSURE_PROBE_INTERVAL_SECONDS = 5.0


def get_event_plane_shard_writer(
    settings: Settings | None = None,
) -> LocalAppendOnlyShardWriter:
    global _event_plane_shard_writer
    if _event_plane_shard_writer is not None:
        return _event_plane_shard_writer
    with _event_plane_shard_writer_lock:
        if _event_plane_shard_writer is None:
            resolved = settings if settings is not None else get_settings()
            _event_plane_shard_writer = LocalAppendOnlyShardWriter(
                root_dir=resolved.event_plane_shards_path,
                max_shard_bytes=resolved.event_plane_shard_max_bytes,
                max_shard_age_seconds=resolved.event_plane_shard_max_age_seconds,
                durability_mode=ShardDurabilityMode.ALWAYS,
            )
    return _event_plane_shard_writer


def _event_plane_manifest_path(*, settings: Settings) -> Path:
    return Path(settings.event_plane_shards_path).parent / "events-index" / "manifest.sqlite"


def get_event_plane_manifest(settings: Settings | None = None) -> SqliteShardManifest:
    global _event_plane_manifest
    if _event_plane_manifest is not None:
        return _event_plane_manifest
    with _event_plane_manifest_lock:
        if _event_plane_manifest is None:
            resolved = settings if settings is not None else get_settings()
            _event_plane_manifest = SqliteShardManifest(
                _event_plane_manifest_path(settings=resolved)
            )
    return _event_plane_manifest


def _record_manifest_lifecycle(
    *,
    project_id: str,
    write_result: ShardWriteResult,
    settings: Settings,
) -> None:
    manifest = get_event_plane_manifest(settings=settings)
    manifest.register_open_shard(
        shard_id=write_result.shard_id,
        project_id=project_id,
        shard_path=str(write_result.shard_path),
    )
    for sealed_id in write_result.sealed_shard_ids:
        try:
            manifest.transition_state(
                shard_id=sealed_id,
                to_state=ShardManifestState.SEALED,
            )
            service_metrics.increment("event_plane.shards.sealed_total")
        except (KeyError, ValueError):
            # Keep ingest fail-open: inconsistent manifest transitions should not fail append.
            continue


def append_events_to_shards(
    *,
    project_id: str,
    received_at: datetime,
    rows: Sequence[Mapping[str, Any]],
    settings: Settings | None = None,
) -> ShardWriteResult | None:
    if not rows:
        return None
    resolved = settings if settings is not None else get_settings()
    writer = get_event_plane_shard_writer(settings=resolved)
    _enforce_event_plane_backpressure_or_raise(
        root_dir=writer.root_dir,
        min_free_bytes=resolved.event_plane_backpressure_min_free_bytes,
        min_free_percent=resolved.event_plane_backpressure_min_free_percent,
    )
    _enforce_event_plane_backlog_or_raise(
        root_dir=writer.root_dir,
        max_pending_shards=resolved.event_plane_backpressure_max_pending_shards,
    )
    result = writer.append_rows(project_id=project_id, received_at=received_at, rows=rows)
    _record_manifest_lifecycle(
        project_id=project_id,
        write_result=result,
        settings=resolved,
    )
    return result


def shutdown_event_plane_shard_writer() -> None:
    global _event_plane_shard_writer, _event_plane_manifest
    with _event_plane_shard_writer_lock:
        writer = _event_plane_shard_writer
        _event_plane_shard_writer = None
        if writer is not None:
            sealed_ids = writer.close_and_seal()
            if sealed_ids:
                try:
                    manifest = get_event_plane_manifest()
                except Exception:
                    manifest = None
                if manifest is not None:
                    for sealed_id in sealed_ids:
                        try:
                            manifest.transition_state(
                                shard_id=sealed_id,
                                to_state=ShardManifestState.SEALED,
                            )
                            service_metrics.increment("event_plane.shards.sealed_total")
                        except (KeyError, ValueError):
                            continue
    with _event_plane_manifest_lock:
        manifest = _event_plane_manifest
        _event_plane_manifest = None
        if manifest is not None:
            manifest.close()
    with _event_plane_backpressure_probe_lock:
        _event_plane_backpressure_probe_cache.clear()


def _enforce_event_plane_backpressure_or_raise(
    *,
    root_dir: Path,
    min_free_bytes: int,
    min_free_percent: int,
) -> None:
    usage = shutil.disk_usage(root_dir)
    free = int(usage.free)
    total = int(usage.total)
    free_percent = (float(free) / float(total) * 100.0) if total > 0 else 0.0
    if free >= int(min_free_bytes) and free_percent >= float(min_free_percent):
        return
    raise EventPlaneBackpressureError(
        "event plane shard append rejected due to low disk headroom "
        f"(free_bytes={free} min_free_bytes={int(min_free_bytes)} "
        f"free_percent={free_percent:.2f} min_free_percent={int(min_free_percent)})"
    )


def _count_shard_files_up_to_limit(root_dir: Path, limit: int) -> int:
    count = 0
    for dir_path, _, file_names in os.walk(root_dir):
        _ = dir_path
        for name in file_names:
            if not name.startswith("shard-") or not name.endswith(".jsonl"):
                continue
            count += 1
            if count > limit:
                return count
    return count


def _probe_pending_shards(root_dir: Path, limit: int) -> int:
    now = time.monotonic()
    key = str(root_dir.resolve())
    with _event_plane_backpressure_probe_lock:
        cached = _event_plane_backpressure_probe_cache.get(key)
        if (
            cached is not None
            and (now - cached[0]) < _EVENT_PLANE_BACKPRESSURE_PROBE_INTERVAL_SECONDS
        ):
            return int(cached[1])
    count = _count_shard_files_up_to_limit(root_dir, limit)
    with _event_plane_backpressure_probe_lock:
        _event_plane_backpressure_probe_cache[key] = (now, int(count))
    return count


def _enforce_event_plane_backlog_or_raise(*, root_dir: Path, max_pending_shards: int) -> None:
    pending = _probe_pending_shards(root_dir, int(max_pending_shards))
    if pending <= int(max_pending_shards):
        return
    raise EventPlaneBackpressureError(
        "event plane shard append rejected due to backlog pressure "
        f"(pending_shards={pending} max_pending_shards={int(max_pending_shards)})"
    )
