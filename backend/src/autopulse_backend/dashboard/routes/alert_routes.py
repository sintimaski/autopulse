from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_dashboard_project
from autopulse_backend.config import get_settings
from autopulse_backend.dashboard.params import (
    FROM_TIMESTAMP_QUERY,
    LIMIT_QUERY,
    OFFSET_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
)
from autopulse_backend.dashboard.serializers import serialize_alert_settings
from autopulse_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from autopulse_backend.database import get_db_session
from autopulse_backend.models import AlertDispatch
from autopulse_backend.repositories.alert_settings import get_or_create_project_alert_settings
from autopulse_backend.schemas import (
    DashboardAlertDispatchesResponse,
    DashboardAlertDispatchItem,
    DashboardAlertSettings,
    DashboardAlertSettingsUpdate,
)

router = APIRouter()


@router.get("/alert-settings", response_model=DashboardAlertSettings)
async def get_dashboard_alert_settings(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAlertSettings:
    settings = get_settings()
    alert_settings = await get_or_create_project_alert_settings(
        session, context.project_id, settings
    )
    await session.commit()
    await session.refresh(alert_settings)
    return serialize_alert_settings(alert_settings)


@router.get("/alert-dispatches", response_model=DashboardAlertDispatchesResponse)
async def get_dashboard_alert_dispatches(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    limit: int = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> DashboardAlertDispatchesResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    filters = [
        AlertDispatch.project_id == context.project_id,
        AlertDispatch.triggered_at >= resolved_from,
        AlertDispatch.triggered_at <= resolved_to,
    ]
    total_result = await session.execute(select(func.count(AlertDispatch.id)).where(*filters))
    total = int(total_result.scalar_one())
    rows = await session.execute(
        select(AlertDispatch)
        .where(*filters)
        .order_by(AlertDispatch.triggered_at.desc(), AlertDispatch.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        DashboardAlertDispatchItem(
            id=dispatch.id,
            alert_type=dispatch.alert_type,
            destination_email=dispatch.destination_email,
            delivered_via=dispatch.delivered_via,
            triggered_at=as_utc_datetime(dispatch.triggered_at),
            window_start=as_utc_datetime(dispatch.window_start),
            window_end=as_utc_datetime(dispatch.window_end),
            detail=dispatch.detail,
        )
        for dispatch in rows.scalars().all()
    ]
    return DashboardAlertDispatchesResponse(total=total, limit=limit, offset=offset, items=items)


@router.put("/alert-settings", response_model=DashboardAlertSettings)
async def update_dashboard_alert_settings(
    payload: DashboardAlertSettingsUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAlertSettings:
    settings = get_settings()
    alert_settings = await get_or_create_project_alert_settings(
        session, context.project_id, settings
    )
    alert_settings.enabled = payload.enabled
    alert_settings.destination_email = payload.destination_email
    alert_settings.error_spike_ratio_threshold = payload.error_spike_ratio_threshold
    alert_settings.error_spike_min_requests = payload.error_spike_min_requests
    alert_settings.error_spike_window_minutes = payload.error_spike_window_minutes
    alert_settings.outage_min_requests = payload.outage_min_requests
    alert_settings.outage_window_minutes = payload.outage_window_minutes
    alert_settings.cooldown_minutes = payload.cooldown_minutes
    await session.commit()
    await session.refresh(alert_settings)
    return serialize_alert_settings(alert_settings)
