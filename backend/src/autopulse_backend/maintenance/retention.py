from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.core.config import Settings
from autopulse_backend.models import ArchivedEvent, Event, ProjectUiSettings


@dataclass(frozen=True, slots=True)
class RetentionCleanupResult:
    cutoff: datetime
    deleted_events: int


async def _archive_events_before_delete(
    *,
    session: AsyncSession,
    project_id,
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
        project_settings = await session.scalar(
            select(ProjectUiSettings).where(ProjectUiSettings.project_id == project_id)
        )
        project_cutoff = resolved_now - timedelta(days=max(1, int(retention_days)))
        if project_settings is not None:
            project_settings.archival_status = "running"
            project_settings.archival_last_error = None
        try:
            await _archive_events_before_delete(
                session=session,
                project_id=project_id,
                cutoff=project_cutoff,
                archived_at=resolved_now,
                enabled=bool(project_settings.archival_enabled) if project_settings else False,
            )
        except Exception as exc:
            if project_settings is not None:
                project_settings.archival_status = "failed"
                project_settings.archival_last_error = exc.__class__.__name__
            raise
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
        if project_settings is not None:
            project_settings.archival_status = "idle"
            project_settings.archival_last_success_at = resolved_now
            project_settings.archival_last_error = None

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
