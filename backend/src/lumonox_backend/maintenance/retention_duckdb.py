from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.core.config import Settings
from lumonox_backend.dashboard.routes.query_bundle import mark_project_dashboard_dirty
from lumonox_backend.maintenance.retention_constants import (
    _DUCKDB_SHRINK_BATCH,
    _DUCKDB_SHRINK_MAX_ITERATIONS,
)
from lumonox_backend.models import ProjectUiSettings
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync, run_duckdb_write_sync
from lumonox_backend.services.event_store import get_duckdb_event_store


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
            await run_duckdb_write_sync(store.checkpoint)
        current_size = await run_duckdb_read_sync(
            store.file_size_bytes,
            duckdb_read_operation="retention_file_size",
        )
        if current_size <= max_bytes:
            break
        over_ratio = max(0.0, float(current_size - max_bytes) / float(max(current_size, 1)))
        batch = max(200, min(max_batch, int(max_batch * max(over_ratio, 0.05))))
        deleted_now = await run_duckdb_write_sync(
            store.delete_oldest_events,
            rows_to_delete=batch,
            project_id=project_id,
        )
        if deleted_now <= 0:
            # Dashboard widget points can dominate file growth under host-metrics-heavy ingest.
            deleted_now = await run_duckdb_write_sync(
                store.delete_oldest_widget_points,
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
            await run_duckdb_write_sync(store.checkpoint)
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
    touched_project_ids: set[UUID] = set()

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
    project_ids_raw = await run_duckdb_read_sync(
        store.list_project_ids,
        duckdb_read_operation="retention_list_project_ids",
    )
    for raw_project_id in project_ids_raw:
        with suppress(ValueError):
            project_id = UUID(str(raw_project_id))
            cutoff = default_cutoff
            if not size_only and project_id in overrides:
                cutoff = resolved_now - timedelta(days=max(1, overrides[project_id]))
            if not size_only:
                deleted_for_project = await run_duckdb_write_sync(
                    store.delete_events_before,
                    cutoff=cutoff,
                    project_id=project_id,
                )
                deleted_total += deleted_for_project
                deleted_widgets = await run_duckdb_write_sync(
                    store.delete_widget_points_before,
                    cutoff=cutoff,
                    project_id=project_id,
                )
                deleted_total += deleted_widgets
                if deleted_for_project > 0 or deleted_widgets > 0:
                    touched_project_ids.add(project_id)

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
            project_count = await run_duckdb_read_sync(
                store.count_events_for_project,
                project_id,
                duckdb_read_operation="retention_count_events",
            )
            overflow = max(0, int(project_count) - int(max_log_rows))
            if overflow > 0:
                deleted_for_project = await run_duckdb_write_sync(
                    store.delete_oldest_events,
                    rows_to_delete=overflow,
                    project_id=project_id,
                )
                deleted_total += deleted_for_project
                if deleted_for_project > 0:
                    touched_project_ids.add(project_id)
        if max_db_size_mb is not None:
            deleted_total += await _duckdb_shrink_under_size_cap(
                max_bytes=int(max_db_size_mb) * 1024 * 1024,
                project_id=project_id,
            )

    duckdb_file_cap_candidates: list[int] = []
    if settings.sqlite_max_db_file_mb is not None:
        duckdb_file_cap_candidates.append(int(settings.sqlite_max_db_file_mb))
    min_ui_mb_result = await session.execute(
        select(func.min(ProjectUiSettings.retention_max_db_size_mb)).where(
            ProjectUiSettings.retention_max_db_size_mb.is_not(None)
        )
    )
    min_ui_mb = min_ui_mb_result.scalar_one_or_none()
    if min_ui_mb is not None:
        duckdb_file_cap_candidates.append(int(min_ui_mb))
    if duckdb_file_cap_candidates:
        deleted_global = await _duckdb_shrink_under_size_cap(
            max_bytes=min(duckdb_file_cap_candidates) * 1024 * 1024,
            project_id=None,
        )
        deleted_total += deleted_global
        if deleted_global > 0:
            for raw_project_id in await run_duckdb_read_sync(
                store.list_project_ids,
                duckdb_read_operation="retention_list_project_ids",
            ):
                with suppress(ValueError):
                    touched_project_ids.add(UUID(str(raw_project_id)))
    for project_id in touched_project_ids:
        await mark_project_dashboard_dirty(project_id)
    return deleted_total
