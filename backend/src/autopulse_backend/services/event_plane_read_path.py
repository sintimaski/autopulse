from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.models import ProjectUiSettings
from autopulse_backend.services.event_plane_parity import resolve_current_snapshot_duckdb_path
from autopulse_backend.services.event_store import (
    DuckDbEventStore,
    event_store_enabled,
    get_duckdb_event_store,
    get_duckdb_read_store_for_path,
)


def select_dashboard_read_store_for_cutover(
    *,
    use_snapshot_read: bool,
    settings: Settings | None = None,
) -> DuckDbEventStore:
    resolved = settings if settings is not None else get_settings()
    if not event_store_enabled(resolved):
        return get_duckdb_event_store()
    if not use_snapshot_read:
        return get_duckdb_event_store()
    if resolved.event_plane_mode != "duckdb_log_shards":
        return get_duckdb_event_store()
    snapshot_db = resolve_current_snapshot_duckdb_path(resolved.event_plane_snapshots_path)
    if snapshot_db is None:
        return get_duckdb_event_store()
    return get_duckdb_read_store_for_path(snapshot_db)


async def resolve_dashboard_read_store(
    *,
    session: AsyncSession,
    project_id: UUID,
    settings: Settings | None = None,
) -> DuckDbEventStore:
    resolved = settings if settings is not None else get_settings()
    use_snapshot_read = bool(
        await session.scalar(
            select(ProjectUiSettings.event_plane_use_snapshot_read).where(
                ProjectUiSettings.project_id == project_id
            )
        )
        or False
    )
    return select_dashboard_read_store_for_cutover(
        use_snapshot_read=use_snapshot_read,
        settings=resolved,
    )
