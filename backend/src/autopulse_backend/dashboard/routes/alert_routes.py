from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from autopulse_backend.repositories.alert_dispatches import record_alert_dispatch
from autopulse_backend.repositories.alert_settings import get_or_create_project_alert_settings
from autopulse_backend.schemas import (
    DashboardAlertCapabilitiesResponse,
    DashboardAlertChannelCapability,
    DashboardAlertDispatchesResponse,
    DashboardAlertDispatchItem,
    DashboardAlertSettings,
    DashboardAlertSettingsUpdate,
    DashboardAlertTestResponse,
)
from autopulse_backend.services.alert_service import (
    AlertSignal,
    build_alert_sender,
)

router = APIRouter()


_REASON_CODE_MESSAGES: dict[str, str] = {
    "provider_timeout": "Provider timed out. Verify provider health and retry later.",
    "timeout": "Request timed out before the provider responded. Verify network and retry.",
    "provider_rejected": "Provider rejected the request. Verify destination and credentials.",
    "provider_unavailable": "Provider returned a 5xx error. Check provider status page.",
    "rate_limited": "Provider rate limited this alert. Retry after cooldown.",
    "network_error": "Transport failed before a response arrived. Check outbound network.",
    "missing_destination": "Destination is missing. Update the alert destination settings.",
    "disabled": "Alert policy is disabled for this project.",
    "unknown_provider": "Email provider is not recognized. Verify ALERT_EMAIL_PROVIDER.",
    "missing_api_key": "Provider API key is missing. Set ALERT_EMAIL_API_KEY.",
    "outbox_unwritable": "File-outbox directory is not writable. Check permissions.",
    "outbox_write_failed": "Failed to write magic-link/alert to outbox file.",
    "sendmail_missing": "sendmail binary not found at configured path.",
    "sendmail_failed": "sendmail exited non-zero. Check local MTA queue and logs.",
    "smtp_failed": "SMTP delivery failed. Check host, port, auth, and TLS settings.",
    "unknown": "Delivery failed for an unspecified reason. See provider metadata.",
}


def _reason_message_for_dispatch(reason_code: str | None) -> str | None:
    if reason_code is None:
        return None
    normalized = reason_code.strip().lower()
    if not normalized:
        return None
    mapped = _REASON_CODE_MESSAGES.get(normalized)
    if mapped is not None:
        return mapped
    # Fall back to a human-ish rendering so the UI never surfaces an opaque code.
    return normalized.replace("_", " ").capitalize()


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
            status=dispatch.status,
            reason_code=dispatch.reason_code,
            reason_message=_reason_message_for_dispatch(dispatch.reason_code),
            attempt_count=int(dispatch.attempt_count),
            triggered_at=as_utc_datetime(dispatch.triggered_at),
            window_start=as_utc_datetime(dispatch.window_start),
            window_end=as_utc_datetime(dispatch.window_end),
            delivered_at=(
                as_utc_datetime(dispatch.delivered_at)
                if dispatch.delivered_at is not None
                else None
            ),
            provider_message_id=dispatch.provider_message_id,
            detail=dispatch.detail,
        )
        for dispatch in rows.scalars().all()
    ]
    return DashboardAlertDispatchesResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/alert-capabilities", response_model=DashboardAlertCapabilitiesResponse)
async def get_dashboard_alert_capabilities() -> DashboardAlertCapabilitiesResponse:
    settings = get_settings()
    mode = (settings.alert_sender_mode or "").strip().lower()
    email_provider = (settings.alert_email_provider or "").strip().lower()
    if not settings.alerts_enabled:
        email_status = "unavailable"
        email_reason = "Alert dispatch is disabled by configuration."
    elif email_provider in {"file", "outbox"}:
        email_status = "active"
        email_reason = (
            "File outbox provider is active; alerts are written to disk "
            f"({settings.alert_email_file_outbox_dir})."
        )
    elif email_provider in {"smtp", "smtp_localhost"} and settings.alert_email_smtp_host:
        email_status = "active"
        email_reason = "SMTP dispatch configured."
    elif email_provider in {"resend", "postmark"} and settings.alert_email_api_key:
        email_status = "active"
        email_reason = f"Email provider {email_provider} configured with API key."
    elif email_provider == "sendmail":
        email_status = "active"
        email_reason = "sendmail provider configured; delivery depends on local MTA."
    elif mode == "stub":
        email_status = "unavailable"
        email_reason = "Alert sender is running in stub mode (no external delivery)."
    else:
        email_status = "unavailable"
        email_reason = (
            "Email provider is not fully configured. Set ALERT_EMAIL_PROVIDER plus the "
            "relevant credentials or outbox directory."
        )
    slack_configured = bool(settings.alert_slack_webhook_url)
    discord_configured = bool(settings.alert_discord_webhook_url)
    webhook_configured = bool(settings.alert_webhook_url)
    slack_active = slack_configured and mode in {"slack", "composite"} and settings.alerts_enabled
    discord_active = (
        discord_configured and mode in {"discord", "composite"} and settings.alerts_enabled
    )
    webhook_active = (
        webhook_configured and mode in {"webhook", "composite"} and settings.alerts_enabled
    )
    channels = [
        DashboardAlertChannelCapability(
            channel="email",
            status=email_status,
            enabled=email_status == "active",
            reason=email_reason,
        ),
        DashboardAlertChannelCapability(
            channel="slack",
            status="active" if slack_active else ("unavailable" if slack_configured else "planned"),
            enabled=slack_active,
            reason=(
                "Slack webhook configured and included in alert_sender_mode."
                if slack_active
                else (
                    "Slack webhook is configured but alert_sender_mode excludes slack."
                    if slack_configured
                    else "Slack delivery is not enabled. Set ALERT_SLACK_WEBHOOK_URL."
                )
            ),
        ),
        DashboardAlertChannelCapability(
            channel="discord",
            status=(
                "active" if discord_active else ("unavailable" if discord_configured else "planned")
            ),
            enabled=discord_active,
            reason=(
                "Discord webhook configured and included in alert_sender_mode."
                if discord_active
                else (
                    "Discord webhook is configured but alert_sender_mode excludes discord."
                    if discord_configured
                    else "Discord delivery is not enabled. Set ALERT_DISCORD_WEBHOOK_URL."
                )
            ),
        ),
        DashboardAlertChannelCapability(
            channel="webhook",
            status=(
                "active" if webhook_active else ("unavailable" if webhook_configured else "planned")
            ),
            enabled=webhook_active,
            reason=(
                "Generic webhook configured and included in alert_sender_mode."
                if webhook_active
                else (
                    "Webhook URL is configured but alert_sender_mode excludes it."
                    if webhook_configured
                    else "Generic webhook delivery is not configured."
                )
            ),
        ),
    ]
    return DashboardAlertCapabilitiesResponse(channels=channels)


@router.post("/alert-test", response_model=DashboardAlertTestResponse)
async def send_test_alert_dispatch(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAlertTestResponse:
    """Send a synthetic alert through the configured sender and record the dispatch row.

    The alert surfaces in the dashboard's dispatch history with an explicit
    ``alert_type="test"`` marker so operators can verify end-to-end delivery
    without waiting for a real error spike.
    """
    settings = get_settings()
    alert_settings = await get_or_create_project_alert_settings(
        session, context.project_id, settings
    )
    now = datetime.now(tz=UTC)
    destination_email = alert_settings.destination_email or settings.alert_default_destination_email
    signal = AlertSignal(
        project_id=context.project_id,
        alert_type="test",
        destination_email=destination_email,
        triggered_at=now,
        window_start=now - timedelta(minutes=1),
        window_end=now,
        detail={
            "note": "Dashboard-triggered test alert.",
            "sender_mode": settings.alert_sender_mode,
        },
    )
    sender = build_alert_sender(settings)
    dispatch_result = await sender.send(signal)
    merged_detail = (
        {**signal.detail, **dispatch_result.detail}
        if dispatch_result.detail is not None
        else signal.detail
    )
    record_alert_dispatch(
        session,
        signal,
        delivered_via=dispatch_result.delivered_via,
        detail=merged_detail,
        status=dispatch_result.status,
        reason_code=dispatch_result.reason_code,
        attempt_count=dispatch_result.attempt_count,
        delivered_at=dispatch_result.delivered_at,
        provider_message_id=dispatch_result.provider_message_id,
    )
    await session.commit()
    return DashboardAlertTestResponse(
        status=dispatch_result.status,
        delivered_via=dispatch_result.delivered_via,
        reason_code=dispatch_result.reason_code,
        reason_message=_reason_message_for_dispatch(dispatch_result.reason_code),
        attempt_count=int(dispatch_result.attempt_count),
        delivered_at=dispatch_result.delivered_at,
        provider_message_id=dispatch_result.provider_message_id,
        destination_email=destination_email,
    )


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
