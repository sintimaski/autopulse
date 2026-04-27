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
