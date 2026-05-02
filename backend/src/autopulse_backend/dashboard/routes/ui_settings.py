from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import (
    ProjectContext,
    authenticate_dashboard_project,
    ensure_dashboard_admin_or_owner,
    ensure_dashboard_not_viewer,
)
from autopulse_backend.config import get_settings
from autopulse_backend.dashboard.repositories.project_ui import get_or_create_project_ui_settings
from autopulse_backend.dashboard.serializers import (
    serialize_retention_settings,
    serialize_theme_settings,
)
from autopulse_backend.database import get_db_session
from autopulse_backend.schemas import (
    DashboardRetentionSettings,
    DashboardRetentionSettingsUpdate,
    DashboardThemeSettings,
    DashboardThemeSettingsUpdate,
)

router = APIRouter()


@router.get("/theme-settings", response_model=DashboardThemeSettings)
async def get_dashboard_theme_settings(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardThemeSettings:
    settings = await get_or_create_project_ui_settings(session, context.project_id)
    await session.commit()
    await session.refresh(settings)
    return serialize_theme_settings(settings)


@router.put("/theme-settings", response_model=DashboardThemeSettings)
async def update_dashboard_theme_settings(
    payload: DashboardThemeSettingsUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[None, Depends(ensure_dashboard_not_viewer)],
) -> DashboardThemeSettings:
    settings = await get_or_create_project_ui_settings(session, context.project_id)
    settings.theme_preference = payload.theme_preference
    settings.exclude_autopulse_traffic = payload.exclude_autopulse_traffic
    await session.commit()
    await session.refresh(settings)
    return serialize_theme_settings(settings)


@router.get("/retention-settings", response_model=DashboardRetentionSettings)
async def get_dashboard_retention_settings(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardRetentionSettings:
    settings = get_settings()
    ui_settings = await get_or_create_project_ui_settings(session, context.project_id)
    await session.commit()
    await session.refresh(ui_settings)
    return serialize_retention_settings(
        ui_settings,
        settings.retention_raw_events_days,
        settings.logs_query_max_window_minutes,
    )


@router.put("/retention-settings", response_model=DashboardRetentionSettings)
async def update_dashboard_retention_settings(
    payload: DashboardRetentionSettingsUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[None, Depends(ensure_dashboard_admin_or_owner)],
) -> DashboardRetentionSettings:
    settings = get_settings()
    ui_settings = await get_or_create_project_ui_settings(session, context.project_id)
    ui_settings.retention_raw_events_days = payload.raw_events_days
    ui_settings.logs_query_max_window_minutes = payload.logs_query_max_window_minutes
    ui_settings.retention_max_db_size_mb = payload.retention_max_db_size_mb
    ui_settings.retention_max_log_rows = payload.retention_max_log_rows
    ui_settings.retention_plan = payload.retention_plan
    ui_settings.archival_enabled = payload.archival_enabled
    ui_settings.archival_mode = payload.archival_mode
    await session.commit()
    await session.refresh(ui_settings)
    return serialize_retention_settings(
        ui_settings,
        settings.retention_raw_events_days,
        settings.logs_query_max_window_minutes,
    )
