"""Roll up SQLite ``metric_buckets`` for dashboard overview traffic series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.dashboard.time_window import as_utc_datetime, hour_bucket, minute_bucket
from lumonox_backend.models import MetricBucket


@dataclass(slots=True)
class MetricBucketDisplayRollup:
    request_count: int = 0
    error_count: int = 0
    latency_total_ms: float = 0.0
    count_2xx: int = 0
    count_3xx: int = 0
    count_4xx: int = 0
    count_5xx: int = 0


async def fetch_metric_bucket_rollups_for_overview(
    session: AsyncSession,
    *,
    project_id: UUID,
    from_timestamp: datetime,
    to_timestamp: datetime,
    use_hourly: bool,
) -> dict[datetime, MetricBucketDisplayRollup]:
    """Sum per-minute SQLite buckets, then fold into the same keys Duck overview uses.

    ``use_hourly`` must match ``overview_use_hourly_buckets`` for the same window so keys align
    with ``duckdb_queries.overview_series``.
    """
    stmt = (
        select(
            MetricBucket.minute_start,
            func.sum(MetricBucket.request_count),
            func.sum(MetricBucket.error_count),
            func.sum(MetricBucket.latency_total_ms),
            func.sum(MetricBucket.count_2xx),
            func.sum(MetricBucket.count_3xx),
            func.sum(MetricBucket.count_4xx),
            func.sum(MetricBucket.count_5xx),
        )
        .where(
            MetricBucket.project_id == project_id,
            MetricBucket.minute_start >= from_timestamp,
            MetricBucket.minute_start <= to_timestamp,
        )
        .group_by(MetricBucket.minute_start)
        .order_by(MetricBucket.minute_start.asc())
    )
    result = await session.execute(stmt)
    bucket_fn = hour_bucket if use_hourly else minute_bucket
    out: dict[datetime, MetricBucketDisplayRollup] = {}
    for (
        minute_start,
        req,
        err,
        lat,
        c2,
        c3,
        c4,
        c5,
    ) in result.all():
        key = bucket_fn(as_utc_datetime(minute_start))
        acc = out.setdefault(key, MetricBucketDisplayRollup())
        acc.request_count += int(req or 0)
        acc.error_count += int(err or 0)
        acc.latency_total_ms += float(lat or 0.0)
        acc.count_2xx += int(c2 or 0)
        acc.count_3xx += int(c3 or 0)
        acc.count_4xx += int(c4 or 0)
        acc.count_5xx += int(c5 or 0)
    return out
