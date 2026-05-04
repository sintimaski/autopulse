from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.dashboard.time_window import as_utc_datetime
from autopulse_backend.models import ErrorGroupAggregate, MetricBucket


@dataclass(frozen=True, slots=True)
class MetricBucketDelta:
    project_id: UUID
    minute_start: datetime
    service_name: str
    environment: str
    request_count: int
    error_count: int
    latency_total_ms: float
    count_2xx: int
    count_3xx: int
    count_4xx: int
    count_5xx: int


@dataclass(frozen=True, slots=True)
class ErrorGroupAggregateDelta:
    project_id: UUID
    group_key: str
    path: str
    exception_type: str | None
    message: str | None
    sample_stack_trace: str | None
    count: int
    first_seen: datetime
    last_seen: datetime


async def upsert_metric_buckets(session: AsyncSession, deltas: list[MetricBucketDelta]) -> None:
    if not deltas:
        return
    for delta in deltas:
        row = await session.scalar(
            select(MetricBucket).where(
                MetricBucket.project_id == delta.project_id,
                MetricBucket.minute_start == delta.minute_start,
                MetricBucket.service_name == delta.service_name,
                MetricBucket.environment == delta.environment,
            )
        )
        if row is None:
            session.add(
                MetricBucket(
                    project_id=delta.project_id,
                    minute_start=delta.minute_start,
                    service_name=delta.service_name,
                    environment=delta.environment,
                    request_count=delta.request_count,
                    error_count=delta.error_count,
                    latency_total_ms=delta.latency_total_ms,
                    count_2xx=delta.count_2xx,
                    count_3xx=delta.count_3xx,
                    count_4xx=delta.count_4xx,
                    count_5xx=delta.count_5xx,
                )
            )
            continue
        row.request_count += delta.request_count
        row.error_count += delta.error_count
        row.latency_total_ms += delta.latency_total_ms
        row.count_2xx += delta.count_2xx
        row.count_3xx += delta.count_3xx
        row.count_4xx += delta.count_4xx
        row.count_5xx += delta.count_5xx
    await session.commit()


async def upsert_error_group_aggregates(
    session: AsyncSession, deltas: list[ErrorGroupAggregateDelta]
) -> None:
    if not deltas:
        return
    for delta in deltas:
        row = await session.scalar(
            select(ErrorGroupAggregate).where(
                ErrorGroupAggregate.project_id == delta.project_id,
                ErrorGroupAggregate.group_key == delta.group_key,
            )
        )
        if row is None:
            session.add(
                ErrorGroupAggregate(
                    project_id=delta.project_id,
                    group_key=delta.group_key,
                    path=delta.path,
                    exception_type=delta.exception_type,
                    message=delta.message,
                    sample_stack_trace=delta.sample_stack_trace,
                    count=delta.count,
                    first_seen=as_utc_datetime(delta.first_seen),
                    last_seen=as_utc_datetime(delta.last_seen),
                )
            )
            continue
        row.count += delta.count
        row_first = as_utc_datetime(row.first_seen)
        delta_first = as_utc_datetime(delta.first_seen)
        delta_last = as_utc_datetime(delta.last_seen)
        row_last = as_utc_datetime(row.last_seen)
        row.first_seen = min(row_first, delta_first)
        if delta_last >= row_last:
            row.last_seen = delta_last
            row.path = delta.path
            row.exception_type = delta.exception_type
            row.message = delta.message
            row.sample_stack_trace = delta.sample_stack_trace
    await session.commit()
