from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta


def as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def resolve_time_window(
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
    window_minutes: int,
    *,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    resolved_to = as_utc_datetime(to_timestamp) if to_timestamp is not None else now_utc
    resolved_from = (
        as_utc_datetime(from_timestamp)
        if from_timestamp is not None
        else resolved_to - timedelta(minutes=window_minutes)
    )
    if resolved_from > resolved_to:
        resolved_from, resolved_to = resolved_to, resolved_from
    return resolved_from, resolved_to


def minute_bucket(dt: datetime) -> datetime:
    return as_utc_datetime(dt).replace(second=0, microsecond=0)


def iter_minute_buckets(start: datetime, end: datetime) -> Iterator[datetime]:
    """Yield UTC minute buckets from start to end, inclusive."""
    current = minute_bucket(start)
    final = minute_bucket(end)
    while current <= final:
        yield current
        current = current + timedelta(minutes=1)


def hour_bucket(dt: datetime) -> datetime:
    return as_utc_datetime(dt).replace(minute=0, second=0, microsecond=0)


def iter_hour_buckets(start: datetime, end: datetime) -> Iterator[datetime]:
    """Yield UTC hour buckets from start to end, inclusive."""
    current = hour_bucket(start)
    final = hour_bucket(end)
    while current <= final:
        yield current
        current = current + timedelta(hours=1)


def overview_use_hourly_buckets(from_timestamp: datetime, to_timestamp: datetime) -> bool:
    """Use hour-sized buckets for long windows to cut DuckDB GROUP BY cardinality."""
    return (as_utc_datetime(to_timestamp) - as_utc_datetime(from_timestamp)) > timedelta(hours=48)
