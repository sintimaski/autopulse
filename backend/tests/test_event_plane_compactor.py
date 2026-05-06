from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from autopulse_backend.services.event_plane_compactor import EventPlaneCompactor
from autopulse_backend.services.event_plane_manifest import (
    ShardManifestState,
    SqliteShardManifest,
)


def _write_shard(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _register_sealed(
    manifest: SqliteShardManifest, *, shard_id: str, project_id: str, shard_path: Path
) -> None:
    manifest.register_open_shard(
        shard_id=shard_id,
        project_id=project_id,
        shard_path=str(shard_path),
    )
    manifest.transition_state(shard_id=shard_id, to_state=ShardManifestState.SEALED)


def test_compactor_builds_snapshot_and_marks_shards_compacted(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "events-index" / "manifest.sqlite")
    snapshots_root = tmp_path / "events-duckdb"
    now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
    shard_one = tmp_path / "events-log" / "p1" / "2026/05/05/22" / "shard-1.jsonl"
    shard_two = tmp_path / "events-log" / "p1" / "2026/05/05/22" / "shard-2.jsonl"
    _write_shard(
        shard_one,
        [
            {
                "project_id": "p1",
                "timestamp": now,
                "received_at": now,
                "sdk_version": "1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/a",
                "status_code": 200,
                "latency_ms": 1.2,
                "payload": {"x": 1},
            }
        ],
    )
    _write_shard(
        shard_two,
        [
            {
                "project_id": "p1",
                "timestamp": now,
                "received_at": now,
                "sdk_version": "1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "POST",
                "path": "/b",
                "status_code": 201,
                "latency_ms": 2.3,
                "payload": {"y": 2},
            }
        ],
    )
    _register_sealed(manifest, shard_id="s1", project_id="p1", shard_path=shard_one)
    _register_sealed(manifest, shard_id="s2", project_id="p1", shard_path=shard_two)
    compactor = EventPlaneCompactor(manifest=manifest, snapshots_root=snapshots_root)

    result = compactor.compact_once()

    assert result.snapshot_version is not None
    assert result.compacted_shards == 2
    assert result.compacted_rows == 2
    assert result.published_snapshot_path is not None
    assert (result.published_snapshot_path / "COMPLETE").is_file()
    current_snapshot = compactor.resolve_current_snapshot_path()
    assert current_snapshot == result.published_snapshot_path
    assert manifest.get_shard("s1") is not None
    assert manifest.get_shard("s1").state == ShardManifestState.COMPACTED  # type: ignore[union-attr]
    assert manifest.get_shard("s2") is not None
    assert manifest.get_shard("s2").state == ShardManifestState.COMPACTED  # type: ignore[union-attr]
    db_path = result.published_snapshot_path / "events.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        count = int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    finally:
        conn.close()
    assert count == 2
    manifest.close()


def test_compactor_is_idempotent_after_compacted(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "events-index" / "manifest.sqlite")
    snapshots_root = tmp_path / "events-duckdb"
    now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
    shard = tmp_path / "events-log" / "p1" / "2026/05/05/22" / "shard-1.jsonl"
    _write_shard(
        shard,
        [
            {
                "project_id": "p1",
                "timestamp": now,
                "received_at": now,
                "sdk_version": "1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/a",
                "status_code": 200,
                "latency_ms": 1.2,
                "payload": {},
            }
        ],
    )
    _register_sealed(manifest, shard_id="s1", project_id="p1", shard_path=shard)
    compactor = EventPlaneCompactor(manifest=manifest, snapshots_root=snapshots_root)

    first = compactor.compact_once()
    second = compactor.compact_once()

    assert first.compacted_rows == 1
    assert second.compacted_rows == 0
    assert second.snapshot_version is None
    manifest.close()


def test_compactor_resumes_compacting_state_after_restart(tmp_path: Path) -> None:
    manifest_path = tmp_path / "events-index" / "manifest.sqlite"
    snapshots_root = tmp_path / "events-duckdb"
    now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
    shard = tmp_path / "events-log" / "p1" / "2026/05/05/22" / "shard-1.jsonl"
    _write_shard(
        shard,
        [
            {
                "project_id": "p1",
                "timestamp": now,
                "received_at": now,
                "sdk_version": "1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/a",
                "status_code": 200,
                "latency_ms": 1.2,
                "payload": {},
            }
        ],
    )
    m1 = SqliteShardManifest(manifest_path)
    _register_sealed(m1, shard_id="s1", project_id="p1", shard_path=shard)
    m1.transition_state(shard_id="s1", to_state=ShardManifestState.COMPACTING)
    m1.close()

    m2 = SqliteShardManifest(manifest_path)
    compactor = EventPlaneCompactor(manifest=m2, snapshots_root=snapshots_root)
    result = compactor.compact_once()

    assert result.compacted_rows == 1
    assert m2.get_shard("s1") is not None
    assert m2.get_shard("s1").state == ShardManifestState.COMPACTED  # type: ignore[union-attr]
    m2.close()


def test_failed_compaction_build_is_not_published(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "events-index" / "manifest.sqlite")
    snapshots_root = tmp_path / "events-duckdb"
    missing_shard = tmp_path / "events-log" / "p1" / "2026/05/05/22" / "missing.jsonl"
    _register_sealed(manifest, shard_id="s1", project_id="p1", shard_path=missing_shard)
    compactor = EventPlaneCompactor(manifest=manifest, snapshots_root=snapshots_root)

    with pytest.raises(FileNotFoundError):
        compactor.compact_once()

    assert compactor.list_published_snapshots() == []
    assert manifest.get_shard("s1") is not None
    assert manifest.get_shard("s1").state == ShardManifestState.COMPACTING  # type: ignore[union-attr]
    manifest.close()


def test_current_pointer_is_atomic_for_concurrent_reads(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "events-index" / "manifest.sqlite")
    snapshots_root = tmp_path / "events-duckdb"
    compactor = EventPlaneCompactor(manifest=manifest, snapshots_root=snapshots_root)
    now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
    shard_one = tmp_path / "events-log" / "p1" / "2026/05/05/22" / "shard-1.jsonl"
    shard_two = tmp_path / "events-log" / "p1" / "2026/05/05/22" / "shard-2.jsonl"
    _write_shard(
        shard_one,
        [
            {
                "project_id": "p1",
                "timestamp": now,
                "received_at": now,
                "sdk_version": "1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/a",
                "status_code": 200,
                "latency_ms": 1.0,
                "payload": {},
            }
        ],
    )
    _register_sealed(manifest, shard_id="s1", project_id="p1", shard_path=shard_one)
    first = compactor.compact_once()
    assert first.published_snapshot_path is not None
    _write_shard(
        shard_two,
        [
            {
                "project_id": "p1",
                "timestamp": now,
                "received_at": now,
                "sdk_version": "1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "POST",
                "path": "/b",
                "status_code": 201,
                "latency_ms": 2.0,
                "payload": {},
            }
        ],
    )
    _register_sealed(manifest, shard_id="s2", project_id="p1", shard_path=shard_two)

    original = compactor._write_current_pointer_atomically

    def _slow_write(payload: dict[str, object]) -> None:
        time.sleep(0.05)
        original(payload)

    compactor._write_current_pointer_atomically = _slow_write  # type: ignore[method-assign]
    observed: list[Path] = []
    stop = threading.Event()

    def _reader() -> None:
        while not stop.is_set():
            path = compactor.resolve_current_snapshot_path()
            if path is not None:
                observed.append(path)
            time.sleep(0.001)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    second = compactor.compact_once()
    stop.set()
    reader.join(timeout=1)

    assert second.published_snapshot_path is not None
    assert observed
    allowed = {first.published_snapshot_path, second.published_snapshot_path}
    assert set(observed).issubset(allowed)
    assert all((path / "COMPLETE").is_file() for path in observed)
    assert compactor.resolve_current_snapshot_path() == second.published_snapshot_path
    manifest.close()


def test_compactor_respects_max_shards_per_run(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "events-index" / "manifest.sqlite")
    snapshots_root = tmp_path / "events-duckdb"
    now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
    for idx in range(4):
        shard_path = tmp_path / "events-log" / "p1" / "2026/05/05/22" / f"shard-{idx}.jsonl"
        _write_shard(
            shard_path,
            [
                {
                    "project_id": "p1",
                    "timestamp": now,
                    "received_at": now,
                    "sdk_version": "1.0",
                    "type": "request",
                    "service_name": "api",
                    "environment": "test",
                    "method": "GET",
                    "path": f"/{idx}",
                    "status_code": 200,
                    "latency_ms": 1.0,
                    "payload": {},
                }
            ],
        )
        _register_sealed(manifest, shard_id=f"s{idx}", project_id="p1", shard_path=shard_path)
    compactor = EventPlaneCompactor(
        manifest=manifest, snapshots_root=snapshots_root, max_shards_per_run=2
    )
    first = compactor.compact_once()
    second = compactor.compact_once()

    assert first.compacted_shards == 2
    assert second.compacted_shards == 2
    manifest.close()


def test_compactor_selects_sealed_shards_fairly_across_projects(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "events-index" / "manifest.sqlite")
    snapshots_root = tmp_path / "events-duckdb"
    now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
    shard_specs = [
        ("a1", "project-a"),
        ("a2", "project-a"),
        ("a3", "project-a"),
        ("b1", "project-b"),
        ("c1", "project-c"),
    ]
    for shard_id, project_id in shard_specs:
        shard_path = tmp_path / "events-log" / project_id / "2026/05/05/22" / f"{shard_id}.jsonl"
        _write_shard(
            shard_path,
            [
                {
                    "project_id": project_id,
                    "timestamp": now,
                    "received_at": now,
                    "sdk_version": "1.0",
                    "type": "request",
                    "service_name": "api",
                    "environment": "test",
                    "method": "GET",
                    "path": f"/{shard_id}",
                    "status_code": 200,
                    "latency_ms": 1.0,
                    "payload": {},
                }
            ],
        )
        _register_sealed(manifest, shard_id=shard_id, project_id=project_id, shard_path=shard_path)
    compactor = EventPlaneCompactor(
        manifest=manifest, snapshots_root=snapshots_root, max_shards_per_run=3
    )
    first = compactor.compact_once()
    assert first.compacted_shards == 3

    assert manifest.get_shard("a1") is not None
    assert manifest.get_shard("a1").state == ShardManifestState.COMPACTED  # type: ignore[union-attr]
    assert manifest.get_shard("b1") is not None
    assert manifest.get_shard("b1").state == ShardManifestState.COMPACTED  # type: ignore[union-attr]
    assert manifest.get_shard("c1") is not None
    assert manifest.get_shard("c1").state == ShardManifestState.COMPACTED  # type: ignore[union-attr]
    assert manifest.get_shard("a2") is not None
    assert manifest.get_shard("a2").state == ShardManifestState.SEALED  # type: ignore[union-attr]
    assert manifest.get_shard("a3") is not None
    assert manifest.get_shard("a3").state == ShardManifestState.SEALED  # type: ignore[union-attr]
    manifest.close()


def test_compactor_tick_runs_multiple_passes_up_to_budget(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "events-index" / "manifest.sqlite")
    snapshots_root = tmp_path / "events-duckdb"
    now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
    for idx in range(5):
        shard_path = tmp_path / "events-log" / "p1" / "2026/05/05/22" / f"tick-{idx}.jsonl"
        _write_shard(
            shard_path,
            [
                {
                    "project_id": "p1",
                    "timestamp": now,
                    "received_at": now,
                    "sdk_version": "1.0",
                    "type": "request",
                    "service_name": "api",
                    "environment": "test",
                    "method": "GET",
                    "path": f"/tick-{idx}",
                    "status_code": 200,
                    "latency_ms": 1.0,
                    "payload": {},
                }
            ],
        )
        _register_sealed(manifest, shard_id=f"tick-{idx}", project_id="p1", shard_path=shard_path)
    compactor = EventPlaneCompactor(
        manifest=manifest,
        snapshots_root=snapshots_root,
        max_shards_per_run=2,
        max_runs_per_tick=3,
    )

    tick = compactor.compact_tick()

    assert len(tick.runs) == 3
    assert tick.compacted_shards == 5
    assert tick.compacted_rows == 5
    manifest.close()


def test_compactor_tick_budget_improves_per_tick_throughput(tmp_path: Path) -> None:
    def _prepare_manifest(root: Path) -> tuple[SqliteShardManifest, Path]:
        manifest = SqliteShardManifest(root / "events-index" / "manifest.sqlite")
        snapshots_root = root / "events-duckdb"
        now = datetime(2026, 5, 5, 22, 0, tzinfo=UTC).isoformat()
        for idx in range(8):
            shard_path = root / "events-log" / "p1" / "2026/05/05/22" / f"load-{idx}.jsonl"
            _write_shard(
                shard_path,
                [
                    {
                        "project_id": "p1",
                        "timestamp": now,
                        "received_at": now,
                        "sdk_version": "1.0",
                        "type": "request",
                        "service_name": "api",
                        "environment": "test",
                        "method": "GET",
                        "path": f"/load-{idx}",
                        "status_code": 200,
                        "latency_ms": 1.0,
                        "payload": {},
                    }
                ],
            )
            _register_sealed(
                manifest, shard_id=f"load-{idx}", project_id="p1", shard_path=shard_path
            )
        return manifest, snapshots_root

    manifest_low, snapshots_low = _prepare_manifest(tmp_path / "low")
    low_budget = EventPlaneCompactor(
        manifest=manifest_low,
        snapshots_root=snapshots_low,
        max_shards_per_run=2,
        max_runs_per_tick=1,
    )
    low_tick = low_budget.compact_tick()

    manifest_high, snapshots_high = _prepare_manifest(tmp_path / "high")
    high_budget = EventPlaneCompactor(
        manifest=manifest_high,
        snapshots_root=snapshots_high,
        max_shards_per_run=2,
        max_runs_per_tick=4,
    )
    high_tick = high_budget.compact_tick()

    assert low_tick.compacted_shards == 2
    assert high_tick.compacted_shards == 8
    assert high_tick.compacted_shards > low_tick.compacted_shards
    assert high_tick.compacted_rows == 8
    manifest_low.close()
    manifest_high.close()
