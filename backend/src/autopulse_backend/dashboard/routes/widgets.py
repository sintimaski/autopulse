from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_dashboard_project
from autopulse_backend.dashboard.params import (
    FROM_TIMESTAMP_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
)
from autopulse_backend.dashboard.time_window import resolve_time_window
from autopulse_backend.database import get_db_session
from autopulse_backend.repositories import dashboard_widgets as dashboard_widgets_repo
from autopulse_backend.schemas import (
    DashboardWidgetDefinition,
    DashboardWidgetPoint,
    DashboardWidgetsResponse,
)

router = APIRouter()


@router.get("/widgets", response_model=DashboardWidgetsResponse)
async def get_dashboard_widgets(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
) -> DashboardWidgetsResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    definitions = await dashboard_widgets_repo.list_widget_definitions(
        session, project_id=context.project_id
    )
    points = await dashboard_widgets_repo.list_widget_points(
        session,
        project_id=context.project_id,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
    )
    return DashboardWidgetsResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        definitions=[
            DashboardWidgetDefinition(
                widget_id=item.widget_id,
                type=item.widget_type,
                title=item.title,
                description=item.description,
                order=item.display_order,
                config=item.config or {},
            )
            for item in definitions
            if item.widget_type
            in {"card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"}
        ],
        points=[
            DashboardWidgetPoint(
                widget_id=item.widget_id,
                timestamp=item.timestamp,
                label=item.label,
                value=item.value,
            )
            for item in points
        ],
    )
