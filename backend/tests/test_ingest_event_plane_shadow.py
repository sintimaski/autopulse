from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from autopulse_backend.core.config import Settings
from autopulse_backend.metrics import service_metrics
from autopulse_backend.services.event_plane_shards import (
    EventPlaneBackpressureError,
    ShardWriteResult,
)
from autopulse_backend.services.ingest_service import (
    _maybe_shadow_write_event_plane_shards,
    _record_shadow_window_parity,
    _shadow_parity_window_counts,
)


def _base_settings(*, event_plane_mode: str) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./x.db",
        event_store="duckdb",
        event_store_duckdb_path="./.autopulse/events.duckdb",
        event_plane_mode=event_plane_mode,
    )


def test_shadow_write_appends_and_increments_success_metric(monkeypatch) -> None:
    baseline = service_metrics.snapshot().get("event_plane.shards.appended_total", 0)
    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.get_settings",
        lambda: _base_settings(event_plane_mode="duckdb_log_shards"),
    )

    def _append_events_to_shards(**_: object) -> ShardWriteResult:
        return ShardWriteResult(
            shard_path=Path("/tmp/shard.jsonl"),
            shard_id="s1",
            records_appended=2,
            bytes_appended=42,
            rotated=False,
            fsync_performed=True,
        )

    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.append_events_to_shards",
        _append_events_to_shards,
    )

    asyncio.run(
        _maybe_shadow_write_event_plane_shards(
            project_id=uuid4(),
            received_at=datetime.now(tz=UTC),
            rows=[{"path": "/ok"}, {"path": "/ok2"}],
        )
    )
    after = service_metrics.snapshot().get("event_plane.shards.appended_total", 0)
    assert after == baseline + 2


def test_shadow_write_failure_is_swallowed_and_counts_failure_metric(monkeypatch) -> None:
    baseline = service_metrics.snapshot().get("event_plane.shards.append_failed_total", 0)
    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.get_settings",
        lambda: _base_settings(event_plane_mode="duckdb_log_shards"),
    )

    def _append_events_to_shards(**_: object) -> ShardWriteResult:
        raise RuntimeError("simulated shard write failure")

    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.append_events_to_shards",
        _append_events_to_shards,
    )

    asyncio.run(
        _maybe_shadow_write_event_plane_shards(
            project_id=uuid4(),
            received_at=datetime.now(tz=UTC),
            rows=[{"path": "/ok"}],
        )
    )
    after = service_metrics.snapshot().get("event_plane.shards.append_failed_total", 0)
    assert after == baseline + 1


def test_shadow_write_backpressure_rejection_counts_rejected_metric(monkeypatch) -> None:
    baseline = service_metrics.snapshot().get("event_plane.shards.append_rejected_total", 0)
    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.get_settings",
        lambda: _base_settings(event_plane_mode="duckdb_log_shards"),
    )

    def _append_events_to_shards(**_: object) -> ShardWriteResult:
        raise EventPlaneBackpressureError("low disk")

    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.append_events_to_shards",
        _append_events_to_shards,
    )

    asyncio.run(
        _maybe_shadow_write_event_plane_shards(
            project_id=uuid4(),
            received_at=datetime.now(tz=UTC),
            rows=[{"path": "/ok"}],
        )
    )
    after = service_metrics.snapshot().get("event_plane.shards.append_rejected_total", 0)
    assert after == baseline + 1


def test_shadow_write_skips_when_event_plane_mode_not_log_shards(monkeypatch) -> None:
    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.get_settings",
        lambda: _base_settings(event_plane_mode="duckdb_single_writer"),
    )

    def _append_events_to_shards(**_: object) -> ShardWriteResult:
        raise AssertionError("append_events_to_shards should not run in single-writer mode")

    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.append_events_to_shards",
        _append_events_to_shards,
    )

    asyncio.run(
        _maybe_shadow_write_event_plane_shards(
            project_id=uuid4(),
            received_at=datetime.now(tz=UTC),
            rows=[{"path": "/ok"}],
        )
    )


def test_shadow_write_tracks_count_mismatch_metric(monkeypatch) -> None:
    baseline = service_metrics.snapshot().get("event_plane.shards.shadow_count_mismatch_total", 0)
    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.get_settings",
        lambda: _base_settings(event_plane_mode="duckdb_log_shards"),
    )

    def _append_events_to_shards(**_: object) -> ShardWriteResult:
        return ShardWriteResult(
            shard_path=Path("/tmp/shard.jsonl"),
            shard_id="s1",
            records_appended=1,
            bytes_appended=42,
            rotated=False,
            fsync_performed=True,
        )

    monkeypatch.setattr(
        "autopulse_backend.services.ingest_service.append_events_to_shards",
        _append_events_to_shards,
    )

    asyncio.run(
        _maybe_shadow_write_event_plane_shards(
            project_id=uuid4(),
            received_at=datetime.now(tz=UTC),
            rows=[{"path": "/ok"}, {"path": "/ok2"}],
        )
    )
    after = service_metrics.snapshot().get("event_plane.shards.shadow_count_mismatch_total", 0)
    assert after == baseline + 1


def test_shadow_window_parity_match_increments_metric() -> None:
    _shadow_parity_window_counts.clear()
    baseline = service_metrics.snapshot().get("event_plane.shards.shadow_window_match_total", 0)
    project_id = uuid4()
    received_at = datetime(2026, 5, 5, 21, 30, tzinfo=UTC)

    _record_shadow_window_parity(
        project_id=project_id,
        received_at=received_at,
        authoritative_rows=2,
        shadow_rows=2,
    )
    after = service_metrics.snapshot().get("event_plane.shards.shadow_window_match_total", 0)
    assert after == baseline + 1


def test_shadow_window_parity_mismatch_increments_metric() -> None:
    _shadow_parity_window_counts.clear()
    baseline = service_metrics.snapshot().get("event_plane.shards.shadow_window_mismatch_total", 0)
    project_id = uuid4()
    received_at = datetime(2026, 5, 5, 21, 31, tzinfo=UTC)

    _record_shadow_window_parity(
        project_id=project_id,
        received_at=received_at,
        authoritative_rows=3,
        shadow_rows=1,
    )
    after = service_metrics.snapshot().get("event_plane.shards.shadow_window_mismatch_total", 0)
    assert after == baseline + 1
