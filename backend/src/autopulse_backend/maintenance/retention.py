from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.core.config import Settings
from autopulse_backend.maintenance.retention_deletes import (
    _archive_events_before_delete,
)
from autopulse_backend.maintenance.retention_duckdb import _apply_duckdb_retention
from autopulse_backend.maintenance.retention_sqlite import (
    _apply_embedded_sqlite_global_file_cap,
    _apply_project_rotation_limits,
    _resolve_sqlite_db_path,
    _sqlite_db_disk_footprint_bytes,
    _vacuum_sqlite_db_file,
)
from autopulse_backend.models import Event, ProjectUiSettings
from autopulse_backend.services.duckdb_async import run_duckdb_read_sync, run_duckdb_write_sync
from autopulse_backend.services.event_store import event_store_enabled, get_duckdb_event_store


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
    size_only = bool(
        settings.sqlite_size_retention_only and settings.database_url.startswith("sqlite")
    )

    # Embedded/local mode can prefer "latest logs preserved by size": delete oldest rows only
    # when the SQLite file exceeds configured caps, and skip age-based sweeping.
    if not size_only:
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
    if event_store_enabled(settings):
        stale_count += await _apply_duckdb_retention(
            session=session,
            settings=settings,
            resolved_now=resolved_now,
            default_cutoff=default_cutoff,
            size_only=size_only,
        )
    stale_count += await _apply_project_rotation_limits(session=session, settings=settings)

    sqlite_file_cap_candidates: list[int] = []
    if settings.embedded_sqlite_max_db_file_mb is not None:
        sqlite_file_cap_candidates.append(int(settings.embedded_sqlite_max_db_file_mb))
    min_ui_mb_result = await session.execute(
        select(func.min(ProjectUiSettings.retention_max_db_size_mb)).where(
            ProjectUiSettings.retention_max_db_size_mb.is_not(None)
        )
    )
    min_ui_mb = min_ui_mb_result.scalar_one_or_none()
    if min_ui_mb is not None:
        sqlite_file_cap_candidates.append(int(min_ui_mb))
    effective_sqlite_file_cap_mb = (
        min(sqlite_file_cap_candidates) if sqlite_file_cap_candidates else None
    )
    if effective_sqlite_file_cap_mb is not None:
        stale_count += await _apply_embedded_sqlite_global_file_cap(
            session=session,
            settings=settings,
            cap_mb=int(effective_sqlite_file_cap_mb),
        )
    await session.commit()
    return RetentionCleanupResult(cutoff=default_cutoff, deleted_events=stale_count)


async def sqlite_retention_pressure_pending(
    session: AsyncSession,
    settings: Settings,
) -> bool:
    """True when SQLite file size or per-project event row caps already exceed configured limits.

    Used to trigger ``run_retention_cleanup_once`` between scheduled runs; keep checks cheap
    (one grouped count query plus ``stat`` on the DB file).
    """
    sqlite_db_path = _resolve_sqlite_db_path(settings.database_url)
    if sqlite_db_path is None:
        return False

    file_cap_mb_candidates: list[int] = []
    if settings.embedded_sqlite_max_db_file_mb is not None:
        file_cap_mb_candidates.append(int(settings.embedded_sqlite_max_db_file_mb))
    all_ui_mb = await session.execute(
        select(ProjectUiSettings.retention_max_db_size_mb).where(
            ProjectUiSettings.retention_max_db_size_mb.is_not(None)
        )
    )
    file_cap_mb_candidates.extend(int(row[0]) for row in all_ui_mb.all())
    if file_cap_mb_candidates:
        min_cap_mb = min(file_cap_mb_candidates)
        try:
            size_bytes = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
        except OSError:
            size_bytes = 0
        if size_bytes > min_cap_mb * 1024 * 1024:
            return True

    overflow = await session.execute(
        select(ProjectUiSettings.retention_max_log_rows, func.count(Event.id))
        .join(Event, Event.project_id == ProjectUiSettings.project_id)
        .where(ProjectUiSettings.retention_max_log_rows.is_not(None))
        .group_by(ProjectUiSettings.project_id, ProjectUiSettings.retention_max_log_rows)
    )
    return any(int(event_count) > int(max_log_rows) for max_log_rows, event_count in overflow.all())


async def retention_pressure_pending(
    session: AsyncSession,
    settings: Settings,
) -> bool:
    if event_store_enabled(settings):
        with suppress(Exception):
            store = get_duckdb_event_store()
            with suppress(Exception):
                await run_duckdb_write_sync(store.checkpoint)
            file_cap_mb_candidates: list[int] = []
            if settings.embedded_sqlite_max_db_file_mb is not None:
                file_cap_mb_candidates.append(int(settings.embedded_sqlite_max_db_file_mb))
            all_ui_mb = await session.execute(
                select(ProjectUiSettings.retention_max_db_size_mb).where(
                    ProjectUiSettings.retention_max_db_size_mb.is_not(None)
                )
            )
            file_cap_mb_candidates.extend(int(row[0]) for row in all_ui_mb.all())
            if file_cap_mb_candidates:
                min_cap_mb = min(file_cap_mb_candidates)
                size_bytes = await run_duckdb_read_sync(store.file_size_bytes)
                if size_bytes > min_cap_mb * 1024 * 1024:
                    return True
            all_ui_rows = await session.execute(
                select(
                    ProjectUiSettings.project_id,
                    ProjectUiSettings.retention_max_log_rows,
                ).where(ProjectUiSettings.retention_max_log_rows.is_not(None))
            )
            for project_id, max_rows in all_ui_rows.all():
                if max_rows is None:
                    continue
                count = await run_duckdb_read_sync(store.count_events_for_project, project_id)
                if int(count) > int(max_rows):
                    return True
        return False
    return await sqlite_retention_pressure_pending(session, settings)


__all__ = [
    "RetentionCleanupResult",
    "_resolve_sqlite_db_path",
    "_sqlite_db_disk_footprint_bytes",
    "_vacuum_sqlite_db_file",
    "retention_pressure_pending",
    "run_retention_cleanup_once",
    "sqlite_retention_pressure_pending",
]
