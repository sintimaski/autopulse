from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.database import get_session_maker
from autopulse_backend.metrics import service_metrics
from autopulse_backend.repositories import ingest_reliability as ingest_reliability_repo
from autopulse_backend.repositories.aggregates import (
    ErrorGroupAggregateDelta,
    MetricBucketDelta,
    upsert_error_group_aggregates,
    upsert_metric_buckets,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestAggregatePayload:
    metric_bucket_deltas: list[MetricBucketDelta]
    error_group_deltas: list[ErrorGroupAggregateDelta]
    enqueued_at: datetime
    retry_count: int = 0


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
    session_maker = get_session_maker(settings.database_url)
    while not stop_event.is_set():
        payload = await queue.get()
        if stop_event.is_set():
            break
        metric_bucket_count = len(payload.metric_bucket_deltas)
        error_group_count = len(payload.error_group_deltas)
        try:
            async with session_maker() as session:
                await upsert_metric_buckets(session, payload.metric_bucket_deltas)
                await upsert_error_group_aggregates(session, payload.error_group_deltas)
            service_metrics.increment("ingest.aggregate_worker.succeeded")
        except Exception:
            service_metrics.increment("ingest.aggregate_worker.failed")
            logger.exception(
                "ingest_aggregate_worker_failed",
                extra={
                    "event": "ingest_aggregate_worker_failed",
                    "metric_bucket_deltas": metric_bucket_count,
                    "error_group_deltas": error_group_count,
                    "enqueued_at": payload.enqueued_at.isoformat(),
                    "retry_count": payload.retry_count,
                },
            )
            max_retries = max(0, settings.ingest_aggregate_worker_max_retries)
            if payload.retry_count < max_retries:
                backoff = min(2.0, 0.05 * (2**payload.retry_count))
                await asyncio.sleep(backoff)
                await queue.put(
                    IngestAggregatePayload(
                        metric_bucket_deltas=payload.metric_bucket_deltas,
                        error_group_deltas=payload.error_group_deltas,
                        enqueued_at=payload.enqueued_at,
                        retry_count=payload.retry_count + 1,
                    )
                )
            else:
                service_metrics.increment("ingest.aggregate_worker.dead_lettered")
                try:
                    async with session_maker() as dl_session:
                        await ingest_reliability_repo.insert_aggregate_dead_letter(
                            dl_session,
                            metric_bucket_deltas=payload.metric_bucket_deltas,
                            error_group_deltas=payload.error_group_deltas,
                            last_error="ingest_aggregate_worker_max_retries",
                        )
                except Exception:
                    logger.exception(
                        "ingest_aggregate_dead_letter_persist_failed",
                        extra={"event": "ingest_aggregate_dead_letter_persist_failed"},
                    )


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
