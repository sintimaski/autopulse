from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.models import (
    AlertDispatch,
    ArchivedEvent,
    DashboardWidgetPoint,
    ErrorGroupAggregate,
    Event,
    IngestRateLimitWindow,
    MetricBucket,
)


async def _archive_events_before_delete(
    *,
    session: AsyncSession,
    project_id: UUID,
    cutoff: datetime,
    archived_at: datetime,
    enabled: bool,
) -> int:
    if not enabled:
        return 0
    stale_rows = await session.execute(
        select(
            Event.id,
            Event.project_id,
            Event.timestamp,
            Event.received_at,
            Event.payload,
        ).where(Event.project_id == project_id, Event.received_at < cutoff)
    )
    rows = stale_rows.all()
    if not rows:
        return 0
    existing_ids_result = await session.execute(
        select(ArchivedEvent.original_event_id).where(
            ArchivedEvent.original_event_id.in_([int(row.id) for row in rows])
        )
    )
    existing_ids = {int(value) for value in existing_ids_result.scalars().all()}
    inserted = 0
    for row in rows:
        event_id = int(row.id)
        if event_id in existing_ids:
            continue
        session.add(
            ArchivedEvent(
                original_event_id=event_id,
                project_id=row.project_id,
                timestamp=row.timestamp,
                received_at=row.received_at,
                archived_at=archived_at,
                payload=row.payload,
            )
        )
        inserted += 1
    return inserted


async def _delete_oldest_dashboard_widget_points_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(DashboardWidgetPoint.id)
        .order_by(DashboardWidgetPoint.timestamp.asc(), DashboardWidgetPoint.id.asc())
        .limit(rows_to_delete)
    )
    ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not ids:
        return 0
    await session.execute(delete(DashboardWidgetPoint).where(DashboardWidgetPoint.id.in_(ids)))
    return len(ids)


async def _delete_oldest_metric_buckets_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(MetricBucket.id)
        .order_by(MetricBucket.minute_start.asc(), MetricBucket.id.asc())
        .limit(rows_to_delete)
    )
    ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not ids:
        return 0
    await session.execute(delete(MetricBucket).where(MetricBucket.id.in_(ids)))
    return len(ids)


async def _delete_oldest_archived_events_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(ArchivedEvent.id)
        .order_by(ArchivedEvent.archived_at.asc(), ArchivedEvent.id.asc())
        .limit(rows_to_delete)
    )
    ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not ids:
        return 0
    await session.execute(delete(ArchivedEvent).where(ArchivedEvent.id.in_(ids)))
    return len(ids)


async def _delete_oldest_error_group_aggregates_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(ErrorGroupAggregate.id)
        .order_by(ErrorGroupAggregate.last_seen.asc(), ErrorGroupAggregate.id.asc())
        .limit(rows_to_delete)
    )
    ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not ids:
        return 0
    await session.execute(delete(ErrorGroupAggregate).where(ErrorGroupAggregate.id.in_(ids)))
    return len(ids)


async def _delete_oldest_ingest_rate_limit_windows_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(IngestRateLimitWindow.id)
        .order_by(IngestRateLimitWindow.window_start.asc(), IngestRateLimitWindow.id.asc())
        .limit(rows_to_delete)
    )
    ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not ids:
        return 0
    await session.execute(delete(IngestRateLimitWindow).where(IngestRateLimitWindow.id.in_(ids)))
    return len(ids)


async def _delete_oldest_alert_dispatches_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(AlertDispatch.id)
        .order_by(AlertDispatch.triggered_at.asc(), AlertDispatch.id.asc())
        .limit(rows_to_delete)
    )
    ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not ids:
        return 0
    await session.execute(delete(AlertDispatch).where(AlertDispatch.id.in_(ids)))
    return len(ids)


async def _sqlite_pressure_delete_auxiliary_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    """Delete one batch from the next non-empty aggregate/table (ingest can dwarf raw events)."""
    for delete_batch in (
        _delete_oldest_dashboard_widget_points_batch,
        _delete_oldest_metric_buckets_batch,
        _delete_oldest_archived_events_batch,
        _delete_oldest_error_group_aggregates_batch,
        _delete_oldest_ingest_rate_limit_windows_batch,
        _delete_oldest_alert_dispatches_batch,
    ):
        deleted = await delete_batch(session=session, rows_to_delete=rows_to_delete)
        if deleted > 0:
            return deleted
    return 0


async def _delete_oldest_project_events(
    *,
    session: AsyncSession,
    project_id: UUID,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(Event.id)
        .where(Event.project_id == project_id)
        .order_by(Event.received_at.asc(), Event.id.asc())
        .limit(rows_to_delete)
    )
    event_ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not event_ids:
        return 0
    await session.execute(delete(Event).where(Event.id.in_(event_ids)))
    return len(event_ids)


async def _delete_oldest_events_global_batch(
    *,
    session: AsyncSession,
    rows_to_delete: int,
) -> int:
    if rows_to_delete <= 0:
        return 0
    rows_result = await session.execute(
        select(Event.id).order_by(Event.received_at.asc(), Event.id.asc()).limit(rows_to_delete)
    )
    event_ids = [int(row_id) for row_id in rows_result.scalars().all()]
    if not event_ids:
        return 0
    await session.execute(delete(Event).where(Event.id.in_(event_ids)))
    return len(event_ids)
