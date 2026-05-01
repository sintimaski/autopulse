from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.dashboard.payload_limits import MAX_DASHBOARD_WIDGET_POINTS_RETURNED
from autopulse_backend.models import DashboardWidgetDefinition, DashboardWidgetPoint
from autopulse_backend.services.duckdb_async import run_duckdb_read_sync, run_duckdb_write_sync
from autopulse_backend.services.event_store import (
    event_store_enabled,
    try_get_duckdb_event_store,
)


async def upsert_widget_definitions(
    session: AsyncSession, definitions: list[dict[str, object]]
) -> None:
    if not definitions:
        return
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "sqlite":
        stmt = sqlite_insert(DashboardWidgetDefinition).values(definitions)
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "widget_id"],
            set_={
                "widget_type": stmt.excluded.widget_type,
                "title": stmt.excluded.title,
                "description": stmt.excluded.description,
                "display_order": stmt.excluded.display_order,
                "config": stmt.excluded.config,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)
        return
    if dialect == "postgresql":
        stmt = pg_insert(DashboardWidgetDefinition).values(definitions)
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "widget_id"],
            set_={
                "widget_type": stmt.excluded.widget_type,
                "title": stmt.excluded.title,
                "description": stmt.excluded.description,
                "display_order": stmt.excluded.display_order,
                "config": stmt.excluded.config,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)
        return
    for definition in definitions:
        row = await session.execute(
            select(DashboardWidgetDefinition).where(
                DashboardWidgetDefinition.project_id == definition["project_id"],
                DashboardWidgetDefinition.widget_id == definition["widget_id"],
            )
        )
        existing = row.scalar_one_or_none()
        if existing is None:
            session.add(DashboardWidgetDefinition(**definition))
            continue
        existing.widget_type = str(definition["widget_type"])
        existing.title = str(definition["title"])
        existing.description = (
            str(definition["description"]) if definition.get("description") is not None else None
        )
        existing.display_order = int(definition["display_order"])
        existing.config = (
            dict(definition["config"]) if isinstance(definition.get("config"), dict) else {}
        )
        existing.updated_at = definition["updated_at"]  # type: ignore[assignment]


async def insert_widget_points(session: AsyncSession, points: list[dict[str, object]]) -> None:
    if not points:
        return
    if event_store_enabled():
        store = try_get_duckdb_event_store()
        if store is not None:
            await run_duckdb_write_sync(store.insert_widget_points, points)
            return
    normalized_points: list[dict[str, object]] = []
    for point in points:
        widget_id = point.get("widget_id")
        timestamp = point.get("timestamp")
        value = point.get("value")
        if (
            not isinstance(widget_id, str)
            or timestamp is None
            or not isinstance(value, int | float)
        ):
            continue
        normalized_points.append(
            {
                "project_id": point.get("project_id"),
                "widget_id": widget_id,
                "timestamp": timestamp,
                "label": point.get("label") if isinstance(point.get("label"), str) else None,
                "value": float(value),
            }
        )
    if not normalized_points:
        return
    await session.execute(insert(DashboardWidgetPoint).values(normalized_points))


async def list_widget_definitions(
    session: AsyncSession, *, project_id: UUID
) -> list[DashboardWidgetDefinition]:
    rows = await session.execute(
        select(DashboardWidgetDefinition)
        .where(DashboardWidgetDefinition.project_id == project_id)
        .order_by(
            DashboardWidgetDefinition.display_order.asc(), DashboardWidgetDefinition.widget_id.asc()
        )
    )
    return list(rows.scalars().all())


async def list_widget_points(
    session: AsyncSession,
    *,
    project_id: UUID,
    from_timestamp: datetime,
    to_timestamp: datetime,
    max_rows: int | None = None,
) -> list[DashboardWidgetPoint]:
    cap = int(max_rows) if max_rows is not None else MAX_DASHBOARD_WIDGET_POINTS_RETURNED
    cap = max(100, min(cap, 50_000))
    if event_store_enabled():
        store = try_get_duckdb_event_store()
        if store is not None:
            rows = await run_duckdb_read_sync(
                store.list_widget_points,
                project_id=project_id,
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                max_rows=cap,
            )
            return [
                DashboardWidgetPoint(
                    project_id=project_id,
                    widget_id=widget_id,
                    timestamp=timestamp,
                    label=label,
                    value=value,
                )
                for widget_id, timestamp, label, value in rows
            ]
    rows = await session.execute(
        select(DashboardWidgetPoint)
        .where(
            DashboardWidgetPoint.project_id == project_id,
            DashboardWidgetPoint.timestamp >= from_timestamp,
            DashboardWidgetPoint.timestamp <= to_timestamp,
        )
        .order_by(desc(DashboardWidgetPoint.timestamp), desc(DashboardWidgetPoint.id))
        .limit(cap)
    )
    points = list(rows.scalars().all())
    points.sort(key=lambda p: (p.timestamp, p.widget_id, p.id))
    return points
