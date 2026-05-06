from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from autopulse_backend.services.event_plane_shards import (
    LocalAppendOnlyShardWriter,
    ShardDurabilityMode,
)


def _read_lines(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_append_rows_writes_jsonl_and_fsyncs_in_always_mode(tmp_path: Path, monkeypatch) -> None:
    fsync_calls: list[int] = []
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_shards.os.fsync", fsync_calls.append
    )
    writer = LocalAppendOnlyShardWriter(
        root_dir=tmp_path / "events-log",
        max_shard_bytes=10_000,
        max_shard_age_seconds=300,
        durability_mode=ShardDurabilityMode.ALWAYS,
    )
    try:
        received_at = datetime(2026, 5, 5, 21, 0, 0, tzinfo=UTC)
        result = writer.append_rows(
            project_id="project-1",
            received_at=received_at,
            rows=[{"path": "/ok", "status_code": 200}, {"path": "/fail", "status_code": 500}],
        )
        parsed = _read_lines(result.shard_path)
        assert parsed == [
            {"path": "/ok", "status_code": 200},
            {"path": "/fail", "status_code": 500},
        ]
        assert result.records_appended == 2
        assert result.fsync_performed is True
        assert len(fsync_calls) >= 1
    finally:
        writer.close()


def test_rotates_shard_when_size_limit_is_reached(tmp_path: Path) -> None:
    writer = LocalAppendOnlyShardWriter(
        root_dir=tmp_path / "events-log",
        max_shard_bytes=40,
        max_shard_age_seconds=300,
        durability_mode=ShardDurabilityMode.NONE,
    )
    try:
        received_at = datetime(2026, 5, 5, 21, 0, 0, tzinfo=UTC)
        first = writer.append_rows(
            project_id="project-1",
            received_at=received_at,
            rows=[{"k": "A" * 40}],
        )
        second = writer.append_rows(
            project_id="project-1",
            received_at=received_at,
            rows=[{"k": "B" * 40}],
        )
        assert first.rotated is True
        assert second.rotated is True
        assert first.shard_path != second.shard_path
    finally:
        writer.close()


def test_rotates_shard_when_age_limit_is_reached(tmp_path: Path) -> None:
    ticks = {"now": 100.0}

    def _fake_monotonic() -> float:
        return ticks["now"]

    writer = LocalAppendOnlyShardWriter(
        root_dir=tmp_path / "events-log",
        max_shard_bytes=10_000,
        max_shard_age_seconds=10,
        durability_mode=ShardDurabilityMode.NONE,
        monotonic=_fake_monotonic,
    )
    try:
        received_at = datetime(2026, 5, 5, 21, 0, 0, tzinfo=UTC)
        first = writer.append_rows(
            project_id="project-1",
            received_at=received_at,
            rows=[{"v": 1}],
        )
        ticks["now"] += 11
        second = writer.append_rows(
            project_id="project-1",
            received_at=received_at + timedelta(seconds=11),
            rows=[{"v": 2}],
        )
        assert second.rotated is True
        assert first.shard_path != second.shard_path
    finally:
        writer.close()


def test_close_forces_fsync_even_when_runtime_mode_is_none(tmp_path: Path, monkeypatch) -> None:
    fsync_calls: list[int] = []
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_shards.os.fsync", fsync_calls.append
    )
    writer = LocalAppendOnlyShardWriter(
        root_dir=tmp_path / "events-log",
        max_shard_bytes=10_000,
        max_shard_age_seconds=300,
        durability_mode=ShardDurabilityMode.NONE,
    )
    received_at = datetime(2026, 5, 5, 21, 0, 0, tzinfo=UTC)
    writer.append_rows(
        project_id="project-1",
        received_at=received_at,
        rows=[{"path": "/ok"}],
    )
    assert fsync_calls == []
    writer.close()
    assert len(fsync_calls) == 1
