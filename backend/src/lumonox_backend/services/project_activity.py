"""Project-scoped activity checks shared by ingest and dashboard routes."""

from __future__ import annotations

from contextlib import suppress
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.core.config import Settings
from lumonox_backend.models import Event
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_store import event_store_enabled, try_get_duckdb_event_store


async def project_has_received_any_event(
    session: AsyncSession,
    *,
    project_id: UUID,
    settings: Settings,
) -> bool:
    """True when SQL ``events`` or DuckDB has at least one row for the project."""
    has_sql_event = bool(
        await session.scalar(select(exists().where(Event.project_id == project_id)))
    )
    if has_sql_event:
        return True
    if not event_store_enabled(settings):
        return False
    store = try_get_duckdb_event_store()
    if store is None:
        return False
    with suppress(Exception):
        duckdb_count = await run_duckdb_read_sync(
            store.count_events_for_project,
            project_id,
            duckdb_read_operation="project_activity_count",
        )
        return bool(duckdb_count > 0)
    return False
