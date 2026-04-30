from __future__ import annotations

import asyncio
import sqlite3
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.core.config import Settings, normalize_database_url
from autopulse_backend.models import (
    AlertDispatch,
    ArchivedEvent,
    DashboardWidgetPoint,
    ErrorGroupAggregate,
    Event,
    IngestRateLimitWindow,
    MetricBucket,
    ProjectUiSettings,
)
from autopulse_backend.services.event_store import event_store_enabled, get_duckdb_event_store


@dataclass(frozen=True, slots=True)
class RetentionCleanupResult:
    cutoff: datetime
    deleted_events: int


_SQLITE_SHRINK_BATCH = 5000
_SQLITE_SHRINK_MAX_ITERATIONS = 50_000
_DUCKDB_SHRINK_BATCH = 5000
_DUCKDB_SHRINK_MAX_ITERATIONS = 50_000


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


def _resolve_sqlite_db_path(database_url: str) -> Path | None:
    """Resolve the SQLite file path for retention size checks (matches engine URL normalization)."""
    normalized = normalize_database_url(database_url.strip())
    if not normalized.startswith("sqlite"):
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"sqlite", "sqlite+aiosqlite"}:
        return None
    raw_path = unquote(parsed.path or "")
    if normalized.endswith(":memory:") or raw_path == ":memory:":
        return None
    if not raw_path:
        return None
    # `normalize_database_url` rewrites to an absolute path; URLs often appear as sqlite://///abs/path.
    if raw_path.startswith("//"):
        return Path(raw_path[1:]).resolve()
    if raw_path.startswith("/./") or raw_path.startswith("/../"):
        return Path(raw_path[1:]).resolve()
    if raw_path.startswith("/") and parsed.netloc:
        return Path(raw_path).resolve()
    if raw_path.startswith("/") and not parsed.netloc:
        return Path(raw_path).resolve()
    return Path(raw_path).resolve()


def _sqlite_db_disk_footprint_bytes(db_path: Path) -> int:
    """Bytes on disk for the DB file plus WAL/SHM sidecars (WAL mode)."""
    if not db_path.exists():
        return 0
    base = str(db_path)
    total = 0
    for path in (db_path, Path(base + "-wal"), Path(base + "-shm")):
        if path.exists():
            total += int(path.stat().st_size)
    return total


def _vacuum_sqlite_db_file(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    # Keep VACUUM fail-fast under contention; never block runtime/shutdown for minutes.
    try:
        with sqlite3.connect(str(db_path), timeout=2.0) as connection:
            connection.execute("PRAGMA busy_timeout=2000")
            with suppress(sqlite3.OperationalError):
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
        return db_path.stat().st_size
    except sqlite3.OperationalError:
        # If DB is busy, skip this pass and retry on the next scheduled tick.
        return db_path.stat().st_size if db_path.exists() else 0


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
    project_id,
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


async def _sqlite_shrink_under_size_cap(
    *,
    session: AsyncSession,
    sqlite_db_path: Path,
    max_bytes: int,
    project_id: UUID | None,
) -> int:
    """Delete oldest rows (per-project or globally) plus auxiliary tables until file fits cap."""
    deleted_total = 0
    stall_rounds = 0
    max_batch = _SQLITE_SHRINK_BATCH
    for _ in range(_SQLITE_SHRINK_MAX_ITERATIONS):
        try:
            current_size = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
        except OSError:
            break
        if current_size <= max_bytes:
            break
        over_ratio = max(0.0, float(current_size - max_bytes) / float(max(current_size, 1)))
        # Keep newest data close to the cap: use smaller batches when only slightly over cap.
        batch = max(200, min(max_batch, int(max_batch * max(over_ratio, 0.05))))

        if project_id is not None:
            deleted_now = await _delete_oldest_project_events(
                session=session,
                project_id=project_id,
                rows_to_delete=batch,
            )
        else:
            deleted_now = await _delete_oldest_events_global_batch(
                session=session,
                rows_to_delete=batch,
            )
        if deleted_now > 0:
            deleted_total += deleted_now
            await session.commit()
            _vacuum_sqlite_db_file(sqlite_db_path)
            try:
                current_after_delete = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
            except OSError:
                break
            if current_after_delete <= max_bytes:
                break
            stall_rounds = 0
            continue

        aux_deleted = await _sqlite_pressure_delete_auxiliary_batch(
            session=session,
            rows_to_delete=batch,
        )
        if aux_deleted > 0:
            deleted_total += aux_deleted
            await session.commit()
            _vacuum_sqlite_db_file(sqlite_db_path)
            try:
                current_after_aux = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
            except OSError:
                break
            if current_after_aux <= max_bytes:
                break
            stall_rounds = 0
            continue

        _vacuum_sqlite_db_file(sqlite_db_path)
        try:
            current_after = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
        except OSError:
            break
        if current_after <= max_bytes:
            break
        stall_rounds += 1
        if stall_rounds >= 3:
            break

    if deleted_total > 0:
        _vacuum_sqlite_db_file(sqlite_db_path)
    return deleted_total


async def _apply_project_rotation_limits(
    *,
    session: AsyncSession,
    settings: Settings,
) -> int:
    sqlite_db_path = _resolve_sqlite_db_path(settings.database_url)
    if sqlite_db_path is None:
        return 0

    rotation_settings = (
        await session.execute(
            select(
                ProjectUiSettings.project_id,
                ProjectUiSettings.retention_max_db_size_mb,
                ProjectUiSettings.retention_max_log_rows,
            ).where(
                ProjectUiSettings.retention_max_db_size_mb.is_not(None)
                | ProjectUiSettings.retention_max_log_rows.is_not(None)
            )
        )
    ).all()
    if not rotation_settings:
        return 0

    deleted_total = 0
    for project_id, max_db_size_mb, max_log_rows in rotation_settings:
        if max_log_rows is not None:
            count_result = await session.execute(
                select(func.count(Event.id)).where(Event.project_id == project_id)
            )
            project_count = int(count_result.scalar_one())
            overflow = max(0, project_count - int(max_log_rows))
            deleted_total += await _delete_oldest_project_events(
                session=session,
                project_id=project_id,
                rows_to_delete=overflow,
            )

        if max_db_size_mb is not None:
            max_size_bytes = int(max_db_size_mb) * 1024 * 1024
            deleted_total += await _sqlite_shrink_under_size_cap(
                session=session,
                sqlite_db_path=sqlite_db_path,
                max_bytes=max_size_bytes,
                project_id=project_id,
            )

    return deleted_total


async def _apply_embedded_sqlite_global_file_cap(
    *,
    session: AsyncSession,
    settings: Settings,
    cap_mb: int,
) -> int:
    """Enforce a maximum SQLite **file** size under storage pressure.

    Ingest also grows aggregate and widget tables; they can dominate file size even when
    raw `events` rows are few. After trimming oldest events globally, we trim oldest rows
    from dashboard widget points, per-minute metric buckets, archived events, error group
    aggregates, ingest rate-limit windows, and alert dispatches until the file fits the
    cap (or nothing left to delete).
    """
    sqlite_db_path = _resolve_sqlite_db_path(settings.database_url)
    if sqlite_db_path is None:
        return 0
    max_bytes = int(cap_mb) * 1024 * 1024
    return await _sqlite_shrink_under_size_cap(
        session=session,
        sqlite_db_path=sqlite_db_path,
        max_bytes=max_bytes,
        project_id=None,
    )


async def _duckdb_shrink_under_size_cap(
    *,
    max_bytes: int,
    project_id: UUID | None,
) -> int:
    store = get_duckdb_event_store()
    deleted_total = 0
    stall_rounds = 0
    max_batch = _DUCKDB_SHRINK_BATCH
    for _ in range(_DUCKDB_SHRINK_MAX_ITERATIONS):
        with suppress(Exception):
            await asyncio.to_thread(store.checkpoint)
        current_size = await asyncio.to_thread(store.file_size_bytes)
        if current_size <= max_bytes:
            break
        over_ratio = max(0.0, float(current_size - max_bytes) / float(max(current_size, 1)))
        batch = max(200, min(max_batch, int(max_batch * max(over_ratio, 0.05))))
        deleted_now = await asyncio.to_thread(
            store.delete_oldest_events,
            rows_to_delete=batch,
            project_id=project_id,
        )
        if deleted_now <= 0:
            stall_rounds += 1
            if stall_rounds >= 3:
                break
            continue
        deleted_total += deleted_now
        with suppress(Exception):
            await asyncio.to_thread(store.checkpoint)
        stall_rounds = 0
    return deleted_total


async def _apply_duckdb_retention(
    *,
    session: AsyncSession,
    settings: Settings,
    resolved_now: datetime,
    default_cutoff: datetime,
    size_only: bool,
) -> int:
    with suppress(Exception):
        store = get_duckdb_event_store()
    if "store" not in locals():
        return 0
    deleted_total = 0

    overrides = {
        project_id: int(days)
        for project_id, days in (
            await session.execute(
                select(
                    ProjectUiSettings.project_id,
                    ProjectUiSettings.retention_raw_events_days,
                ).where(ProjectUiSettings.retention_raw_events_days.is_not(None))
            )
        ).all()
        if days is not None
    }
    project_ids_raw = await asyncio.to_thread(store.list_project_ids)
    for raw_project_id in project_ids_raw:
        with suppress(ValueError):
            project_id = UUID(str(raw_project_id))
            cutoff = default_cutoff
            if not size_only and project_id in overrides:
                cutoff = resolved_now - timedelta(days=max(1, overrides[project_id]))
            if not size_only:
                deleted_total += await asyncio.to_thread(
                    store.delete_events_before,
                    cutoff=cutoff,
                    project_id=project_id,
                )

    rotation_settings = (
        await session.execute(
            select(
                ProjectUiSettings.project_id,
                ProjectUiSettings.retention_max_db_size_mb,
                ProjectUiSettings.retention_max_log_rows,
            ).where(
                ProjectUiSettings.retention_max_db_size_mb.is_not(None)
                | ProjectUiSettings.retention_max_log_rows.is_not(None)
            )
        )
    ).all()
    for project_id, max_db_size_mb, max_log_rows in rotation_settings:
        if max_log_rows is not None:
            project_count = await asyncio.to_thread(store.count_events_for_project, project_id)
            overflow = max(0, int(project_count) - int(max_log_rows))
            if overflow > 0:
                deleted_total += await asyncio.to_thread(
                    store.delete_oldest_events,
                    rows_to_delete=overflow,
                    project_id=project_id,
                )
        if max_db_size_mb is not None:
            deleted_total += await _duckdb_shrink_under_size_cap(
                max_bytes=int(max_db_size_mb) * 1024 * 1024,
                project_id=project_id,
            )

    duckdb_file_cap_candidates: list[int] = []
    if settings.embedded_sqlite_max_db_file_mb is not None:
        duckdb_file_cap_candidates.append(int(settings.embedded_sqlite_max_db_file_mb))
    min_ui_mb_result = await session.execute(
        select(func.min(ProjectUiSettings.retention_max_db_size_mb)).where(
            ProjectUiSettings.retention_max_db_size_mb.is_not(None)
        )
    )
    min_ui_mb = min_ui_mb_result.scalar_one_or_none()
    if min_ui_mb is not None:
        duckdb_file_cap_candidates.append(int(min_ui_mb))
    if duckdb_file_cap_candidates:
        deleted_total += await _duckdb_shrink_under_size_cap(
            max_bytes=min(duckdb_file_cap_candidates) * 1024 * 1024,
            project_id=None,
        )
    return deleted_total


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
                await asyncio.to_thread(store.checkpoint)
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
                size_bytes = await asyncio.to_thread(store.file_size_bytes)
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
                count = await asyncio.to_thread(store.count_events_for_project, project_id)
                if int(count) > int(max_rows):
                    return True
        return False
    return await sqlite_retention_pressure_pending(session, settings)
