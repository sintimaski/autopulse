from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.core.config import get_settings
from lumonox_backend.dashboard.params import (
    FROM_TIMESTAMP_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
)
from lumonox_backend.dashboard.studio_showcase import merge_studio_showcase_widgets
from lumonox_backend.dashboard.time_window import resolve_time_window
from lumonox_backend.dashboard.widget_layout import build_widget_layout
from lumonox_backend.dashboard.widget_points_selection import (
    merge_narrow_window_with_infra_lookback,
)
from lumonox_backend.database import get_db_session
from lumonox_backend.repositories import dashboard_widgets as dashboard_widgets_repo
from lumonox_backend.schemas import (
    DashboardWidgetDefinition,
    DashboardWidgetPoint,
    DashboardWidgetsResponse,
)

router = APIRouter()

# Widget definitions persist across sessions; points are tied to ingest timestamps and may
# fall outside the active overview window (e.g. no traffic for 90m). Query a bounded lookback
# so the gallery and bundled `/dashboard/query` still return points for known definitions.
_WIDGET_POINTS_LOOKBACK = timedelta(days=7)


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
    points_from = min(resolved_from, resolved_to - _WIDGET_POINTS_LOOKBACK)
    points_raw = await dashboard_widgets_repo.list_widget_points(
        session,
        project_id=context.project_id,
        from_timestamp=points_from,
        to_timestamp=resolved_to,
    )
    points = merge_narrow_window_with_infra_lookback(
        points_raw,
        resolved_from=resolved_from,
        resolved_to=resolved_to,
    )
    mapped_definitions = [
        DashboardWidgetDefinition(
            widget_id=item.widget_id,
            type=cast(
                Literal["card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"],
                item.widget_type,
            ),
            title=item.title,
            description=item.description,
            order=item.display_order,
            config=item.config or {},
        )
        for item in definitions
        if item.widget_type
        in {"card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"}
    ]
    mapped_points = [
        DashboardWidgetPoint(
            widget_id=item.widget_id,
            timestamp=item.timestamp,
            label=item.label,
            value=item.value,
        )
        for item in points
    ]
    merged_definitions, merged_points = merge_studio_showcase_widgets(
        mapped_definitions,
        mapped_points,
        resolved_from,
        resolved_to,
        demo_enabled=get_settings().studio_showcase_demo_enabled,
    )
    return DashboardWidgetsResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        definitions=merged_definitions,
        points=merged_points,
        layout=build_widget_layout(merged_definitions),
    )
