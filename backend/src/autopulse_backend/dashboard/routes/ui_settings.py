from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.api.routes.health import _build_metrics_snapshot
from autopulse_backend.auth import (
    DashboardAuthSession,
    ProjectContext,
    authenticate_dashboard_project,
    ensure_dashboard_admin_or_owner,
)
from autopulse_backend.auth.dashboard import get_dashboard_auth_session
from autopulse_backend.auth.rbac import require_member_or_above, require_owner_or_admin
from autopulse_backend.core.config import get_settings
from autopulse_backend.dashboard.repositories.project_ui import get_or_create_project_ui_settings
from autopulse_backend.dashboard.serializers import (
    serialize_retention_settings,
    serialize_theme_settings,
)
from autopulse_backend.database import get_db_session
from autopulse_backend.metrics import service_metrics
from autopulse_backend.schemas import (
    DashboardEventPlaneCutoverSettings,
    DashboardEventPlaneCutoverSettingsUpdate,
    DashboardInternalMetricsResponse,
    DashboardRetentionSettings,
    DashboardRetentionSettingsUpdate,
    DashboardThemeSettings,
    DashboardThemeSettingsUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


async def _optional_dashboard_auth_session(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAuthSession | None:
    """Cookie session when present; ``None`` for API-key-only dashboard clients."""
    settings = get_settings()
    return await get_dashboard_auth_session(session=session, settings=settings, request=request)


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
    auth_session: Annotated[DashboardAuthSession | None, Depends(_optional_dashboard_auth_session)],
) -> DashboardThemeSettings:
    settings = await get_or_create_project_ui_settings(session, context.project_id)
    exclude_changed = payload.exclude_autopulse_traffic != settings.exclude_autopulse_traffic
    theme_changed = payload.theme_preference != settings.theme_preference
    if auth_session is not None:
        if exclude_changed:
            require_owner_or_admin(auth_session)
        if theme_changed:
            require_member_or_above(auth_session)
    # API-key-only requests have no cookie session; ``authenticate_dashboard_project`` treats them
    # as operator/owner scope (see ``ProjectContext.membership_role`` on fallback).
    settings.theme_preference = payload.theme_preference
    settings.exclude_autopulse_traffic = payload.exclude_autopulse_traffic
    await session.commit()
    await session.refresh(settings)
    return serialize_theme_settings(settings)


@router.get("/event-plane-cutover", response_model=DashboardEventPlaneCutoverSettings)
async def get_dashboard_event_plane_cutover_settings(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardEventPlaneCutoverSettings:
    settings = await get_or_create_project_ui_settings(session, context.project_id)
    await session.commit()
    await session.refresh(settings)
    return DashboardEventPlaneCutoverSettings(
        use_snapshot_read=bool(settings.event_plane_use_snapshot_read)
    )


@router.put("/event-plane-cutover", response_model=DashboardEventPlaneCutoverSettings)
async def update_dashboard_event_plane_cutover_settings(
    payload: DashboardEventPlaneCutoverSettingsUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_session: Annotated[DashboardAuthSession | None, Depends(_optional_dashboard_auth_session)],
    _: Annotated[None, Depends(ensure_dashboard_admin_or_owner)],
) -> DashboardEventPlaneCutoverSettings:
    settings = await get_or_create_project_ui_settings(session, context.project_id)
    previous = bool(settings.event_plane_use_snapshot_read)
    updated = bool(payload.use_snapshot_read)
    settings.event_plane_use_snapshot_read = updated
    await session.commit()
    await session.refresh(settings)
    if previous != updated:
        service_metrics.increment("event_plane.cutover_toggle_changes_total")
    logger.info(
        "event_plane_project_cutover_toggled",
        extra={
            "event": "event_plane_project_cutover_toggled",
            "project_id": str(context.project_id),
            "previous_use_snapshot_read": previous,
            "use_snapshot_read": updated,
            "actor_email": (auth_session.email if auth_session is not None else None),
        },
    )
    return DashboardEventPlaneCutoverSettings(
        use_snapshot_read=bool(settings.event_plane_use_snapshot_read)
    )


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


@router.get("/internal-metrics", response_model=DashboardInternalMetricsResponse)
async def get_dashboard_internal_metrics(
    request: Request,
    _: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    __: Annotated[None, Depends(ensure_dashboard_admin_or_owner)],
) -> DashboardInternalMetricsResponse:
    settings = get_settings()
    if not settings.internal_metrics_bearer_token:
        return DashboardInternalMetricsResponse(
            enabled=False,
            reason="INTERNAL_METRICS_BEARER_TOKEN is not configured on the server.",
            metrics=None,
        )
    return DashboardInternalMetricsResponse(
        enabled=True,
        reason=None,
        metrics=_build_metrics_snapshot(request),
    )
