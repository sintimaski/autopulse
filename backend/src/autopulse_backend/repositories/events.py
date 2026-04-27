from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.ingestion.exclude_autopulse import (
    append_exclude_autopulse_event_filters,
    resolve_exclude_autopulse_traffic,
)
from autopulse_backend.models import Event


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
    # Include both request and error event rows in the evaluation window.
    # Ingest paths may emit 5xx failures as `type=error`, and excluding them
    # would undercount errors and prevent expected alert dispatches.
    exclude_autopulse_traffic = await resolve_exclude_autopulse_traffic(session, project_id)
    filters = [
        Event.project_id == project_id,
        Event.type.in_(("request", "error")),
        Event.timestamp >= window_start,
        Event.timestamp <= window_end,
    ]
    append_exclude_autopulse_event_filters(
        filters, exclude_autopulse_traffic=exclude_autopulse_traffic
    )
    result = await session.execute(
        select(
            func.count(Event.id),
            func.sum(case((Event.status_code >= 500, 1), else_=0)),
            func.sum(case((Event.status_code < 500, 1), else_=0)),
        ).where(*filters)
    )
    request_count, error_count, success_count = result.one()
    return int(request_count or 0), int(error_count or 0), int(success_count or 0)
