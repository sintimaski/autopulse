from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.metrics import service_metrics
from autopulse_backend.services.event_plane_compactor import (
    CompactionTickResult,
    make_event_plane_compactor,
)
from autopulse_backend.services.event_plane_manifest import ShardManifestState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EventPlaneCompactorWorkerHandle:
    stop_event: asyncio.Event
    task: asyncio.Task[None]

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task.done():
            return
        self.task.cancel()
        try:
            await asyncio.wait_for(self.task, timeout=5.0)
        except (asyncio.CancelledError, TimeoutError):
            logger.warning("Event plane compactor worker stop timed out")


async def _run_compactor_tick_once(settings: Settings) -> CompactionTickResult:
    compactor = make_event_plane_compactor(settings=settings)
    state_counts = compactor.count_shards_by_state()
    service_metrics.set_value(
        "event_plane.shards.open_count",
        int(state_counts.get(ShardManifestState.OPEN, 0)),
    )
    service_metrics.set_value(
        "event_plane.compaction.lag_seconds",
        compactor.compaction_lag_seconds(),
    )
    service_metrics.set_value(
        "event_plane.snapshot.age_seconds",
        compactor.snapshot_age_seconds(),
    )
    started = time.perf_counter()
    try:
        result = await asyncio.to_thread(compactor.compact_tick)
    except Exception:
        service_metrics.increment("event_plane.compaction.failed_total")
        logger.exception("event_plane_compaction_tick_failed")
        raise
    elapsed_s = time.perf_counter() - started
    elapsed_ms = max(1, int(elapsed_s * 1000)) if elapsed_s > 0 else 0
    service_metrics.increment("event_plane.compaction.duration_ms", amount=elapsed_ms)
    if result.compacted_shards > 0:
        service_metrics.increment(
            "event_plane.compaction.compacted_shards_total",
            amount=int(result.compacted_shards),
        )
    if result.compacted_rows > 0:
        service_metrics.increment(
            "event_plane.compaction.compacted_rows_total",
            amount=int(result.compacted_rows),
        )
    state_counts = compactor.count_shards_by_state()
    service_metrics.set_value(
        "event_plane.shards.open_count",
        int(state_counts.get(ShardManifestState.OPEN, 0)),
    )
    service_metrics.set_value(
        "event_plane.compaction.lag_seconds",
        compactor.compaction_lag_seconds(),
    )
    service_metrics.set_value(
        "event_plane.snapshot.age_seconds",
        compactor.snapshot_age_seconds(),
    )
    return result


async def _event_plane_compactor_loop(settings: Settings, stop_event: asyncio.Event) -> None:
    interval = float(settings.event_plane_compactor_interval_seconds)
    while not stop_event.is_set():
        try:
            await _run_compactor_tick_once(settings)
        except Exception:
            logger.exception("event_plane_compactor_loop_tick_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue


def start_event_plane_compactor_worker(
    *, settings: Settings | None = None
) -> EventPlaneCompactorWorkerHandle | None:
    resolved = settings if settings is not None else get_settings()
    if resolved.event_plane_mode != "duckdb_log_shards":
        return None
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        _event_plane_compactor_loop(resolved, stop_event),
        name="autopulse-event-plane-compactor",
    )
    return EventPlaneCompactorWorkerHandle(stop_event=stop_event, task=task)
