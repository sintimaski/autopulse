from __future__ import annotations

import asyncio
from types import SimpleNamespace

from lumonox_backend.core.config import Settings
from lumonox_backend.metrics import service_metrics
from lumonox_backend.services.event_plane_compactor import CompactionTickResult
from lumonox_backend.services.event_plane_compactor_worker import (
    _run_compactor_tick_once,
    start_event_plane_compactor_worker,
)
from lumonox_backend.services.event_plane_manifest import ShardManifestState


def _settings(*, mode: str) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./x.db",
        event_store="duckdb",
        event_store_duckdb_path="./.lumonox/events.duckdb",
        event_plane_mode=mode,
    )


def test_compactor_worker_start_is_mode_gated() -> None:
    disabled = start_event_plane_compactor_worker(settings=_settings(mode="duckdb_single_writer"))
    assert disabled is None


def test_compactor_worker_tick_increments_metrics(monkeypatch) -> None:
    baseline_shards = service_metrics.snapshot().get(
        "event_plane.compaction.compacted_shards_total", 0
    )
    baseline_rows = service_metrics.snapshot().get("event_plane.compaction.compacted_rows_total", 0)
    baseline_duration = service_metrics.snapshot().get("event_plane.compaction.duration_ms", 0)

    fake_compactor = SimpleNamespace(
        count_shards_by_state=lambda: {ShardManifestState.OPEN: 1},
        compaction_lag_seconds=lambda: 7,
        snapshot_age_seconds=lambda: 11,
        compact_tick=lambda: CompactionTickResult(
            runs=(
                SimpleNamespace(compacted_shards=2, compacted_rows=3),  # type: ignore[arg-type]
            )
        ),
    )
    monkeypatch.setattr(
        "lumonox_backend.services.event_plane_compactor_worker.make_event_plane_compactor",
        lambda settings=None: fake_compactor,
    )

    asyncio.run(_run_compactor_tick_once(_settings(mode="duckdb_log_shards")))

    after = service_metrics.snapshot()
    assert after.get("event_plane.compaction.compacted_shards_total", 0) >= baseline_shards + 2
    assert after.get("event_plane.compaction.compacted_rows_total", 0) >= baseline_rows + 3
    assert after.get("event_plane.compaction.duration_ms", 0) >= baseline_duration
