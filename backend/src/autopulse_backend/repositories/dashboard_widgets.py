from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.models import DashboardWidgetDefinition, DashboardWidgetPoint


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
    await session.execute(insert(DashboardWidgetPoint).values(points))


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
    session: AsyncSession, *, project_id: UUID, from_timestamp: datetime, to_timestamp: datetime
) -> list[DashboardWidgetPoint]:
    rows = await session.execute(
        select(DashboardWidgetPoint)
        .where(
            DashboardWidgetPoint.project_id == project_id,
            DashboardWidgetPoint.timestamp >= from_timestamp,
            DashboardWidgetPoint.timestamp <= to_timestamp,
        )
        .order_by(DashboardWidgetPoint.timestamp.asc())
    )
    return list(rows.scalars().all())
