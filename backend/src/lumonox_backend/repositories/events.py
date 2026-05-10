from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from lumonox_backend.core.config import get_settings
from lumonox_backend.ingestion.exclude_lumonox import (
    append_exclude_lumonox_event_filters,
    resolve_exclude_lumonox_traffic,
)
from lumonox_backend.models import Event
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_store import (
    EventStoreFilters,
    event_store_enabled,
    try_get_duckdb_event_store,
)


async def insert_ingest_events(session: AsyncSession, rows: list[Event]) -> int:
    session.add_all(rows)
    await session.commit()
    return len(rows)


async def request_window_counts(
    session: AsyncSession,
    project_id: UUID,
    window_start: datetime,
    window_end: datetime,
) -> tuple[int, int, int]:
    if event_store_enabled(get_settings()):
        exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, project_id)
        filters = EventStoreFilters(
            project_id=project_id,
            from_timestamp=window_start,
            to_timestamp=window_end,
            exclude_lumonox_traffic=exclude_lumonox_traffic,
        )
        store = try_get_duckdb_event_store()
        if store is not None:
            rows = await run_duckdb_read_sync(
                store.fetch_events,
                filters,
                columns="id, status_code, type",
                duckdb_read_operation="events_window_counts",
            )
            request_count = len(rows)
            error_count = sum(
                1
                for _event_id, status_code, event_type in rows
                if event_type == "error" or int(status_code) >= 500
            )
            success_count = max(0, request_count - error_count)
            return request_count, error_count, success_count

    # Include both request and error event rows in the evaluation window.
    # Ingest paths may emit 5xx failures as `type=error`, and excluding them
    # would undercount errors and prevent expected alert dispatches.
    exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, project_id)
    sql_filters: list[ColumnElement[bool]] = [
        Event.project_id == project_id,
        Event.type.in_(("request", "error")),
        Event.timestamp >= window_start,
        Event.timestamp <= window_end,
    ]
    append_exclude_lumonox_event_filters(
        sql_filters, exclude_lumonox_traffic=exclude_lumonox_traffic
    )
    result = await session.execute(
        select(
            func.count(Event.id),
            func.sum(case((Event.status_code >= 500, 1), else_=0)),
            func.sum(case((Event.status_code < 500, 1), else_=0)),
        ).where(*sql_filters)
    )
    request_count, error_count, success_count = result.one()
    return int(request_count or 0), int(error_count or 0), int(success_count or 0)
