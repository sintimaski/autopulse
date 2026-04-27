from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.core.config import Settings
from autopulse_backend.models import Event, ProjectUiSettings


@dataclass(frozen=True, slots=True)
class RetentionCleanupResult:
    cutoff: datetime
    deleted_events: int


async def run_retention_cleanup_once(
    session: AsyncSession,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> RetentionCleanupResult:
    resolved_now = now.astimezone(UTC) if now is not None else datetime.now(tz=UTC)
    default_cutoff = resolved_now - timedelta(days=settings.retention_raw_events_days)
    stale_count = 0

    retention_overrides = await session.execute(
        select(
            ProjectUiSettings.project_id,
            ProjectUiSettings.retention_raw_events_days,
        ).where(ProjectUiSettings.retention_raw_events_days.is_not(None))
    )
    for project_id, retention_days in retention_overrides:
        if retention_days is None:
            continue
        project_cutoff = resolved_now - timedelta(days=max(1, int(retention_days)))
        count_result = await session.execute(
            select(func.count(Event.id)).where(
                Event.project_id == project_id, Event.received_at < project_cutoff
            )
        )
        project_stale = int(count_result.scalar_one())
        if project_stale > 0:
            stale_count += project_stale
            await session.execute(
                delete(Event).where(
                    Event.project_id == project_id, Event.received_at < project_cutoff
                )
            )

    stale_count_result = await session.execute(
        select(func.count(Event.id)).where(
            Event.received_at < default_cutoff,
            Event.project_id.not_in(
                select(ProjectUiSettings.project_id).where(
                    ProjectUiSettings.retention_raw_events_days.is_not(None)
                )
            ),
        )
    )
    default_stale = int(stale_count_result.scalar_one())
    if default_stale > 0:
        stale_count += default_stale
        await session.execute(
            delete(Event).where(
                Event.received_at < default_cutoff,
                Event.project_id.not_in(
                    select(ProjectUiSettings.project_id).where(
                        ProjectUiSettings.retention_raw_events_days.is_not(None)
                    )
                ),
            )
        )
    await session.commit()
    return RetentionCleanupResult(cutoff=default_cutoff, deleted_events=stale_count)
