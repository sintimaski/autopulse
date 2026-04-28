from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.metrics import service_metrics
from autopulse_backend.repositories.aggregates import (
    ErrorGroupAggregateDelta,
    MetricBucketDelta,
    upsert_error_group_aggregates,
    upsert_metric_buckets,
)


@dataclass(frozen=True, slots=True)
class IngestAggregatePayload:
    metric_bucket_deltas: list[MetricBucketDelta]
    error_group_deltas: list[ErrorGroupAggregateDelta]
    enqueued_at: datetime


@dataclass(slots=True)
class IngestAggregateWorkerHandle:
    queue: asyncio.Queue[IngestAggregatePayload]
    stop_event: asyncio.Event
    task: asyncio.Task[None]

    async def stop(self) -> None:
        self.stop_event.set()
        await self.queue.put(
            IngestAggregatePayload(
                metric_bucket_deltas=[],
                error_group_deltas=[],
                enqueued_at=datetime.now(tz=UTC),
            )
        )
        await self.task


_worker_handle: IngestAggregateWorkerHandle | None = None


async def _run_worker(
    *,
    queue: asyncio.Queue[IngestAggregatePayload],
    stop_event: asyncio.Event,
    settings: Settings,
) -> None:
    engine = get_engine(settings.database_url)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    while not stop_event.is_set():
        payload = await queue.get()
        if stop_event.is_set():
            break
        try:
            async with session_maker() as session:
                await upsert_metric_buckets(session, payload.metric_bucket_deltas)
                await upsert_error_group_aggregates(session, payload.error_group_deltas)
            service_metrics.increment("ingest.aggregate_worker.succeeded")
        except Exception:
            service_metrics.increment("ingest.aggregate_worker.failed")


def start_ingest_aggregate_worker(
    settings: Settings | None = None,
) -> IngestAggregateWorkerHandle:
    global _worker_handle
    if _worker_handle is not None:
        return _worker_handle
    resolved = settings or get_settings()
    queue: asyncio.Queue[IngestAggregatePayload] = asyncio.Queue(
        maxsize=max(1, resolved.ingest_async_aggregate_queue_max_size)
    )
    stop_event = asyncio.Event()
    task = asyncio.create_task(_run_worker(queue=queue, stop_event=stop_event, settings=resolved))
    _worker_handle = IngestAggregateWorkerHandle(queue=queue, stop_event=stop_event, task=task)
    return _worker_handle


async def stop_ingest_aggregate_worker() -> None:
    global _worker_handle
    if _worker_handle is None:
        return
    await _worker_handle.stop()
    _worker_handle = None


def enqueue_ingest_aggregate_payload(payload: IngestAggregatePayload) -> bool:
    if _worker_handle is None:
        return False
    try:
        _worker_handle.queue.put_nowait(payload)
    except asyncio.QueueFull:
        service_metrics.increment("ingest.aggregate_worker.queue_full")
        return False
    service_metrics.increment("ingest.aggregate_worker.enqueued")
    return True
