from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.core.config import Settings
from lumonox_backend.models import ProjectAlertSettings


async def get_or_create_project_alert_settings(
    session: AsyncSession, project_id: UUID, settings: Settings
) -> ProjectAlertSettings:
    current = await session.scalar(
        select(ProjectAlertSettings).where(ProjectAlertSettings.project_id == project_id)
    )
    if current is not None:
        return current
    current = ProjectAlertSettings(
        project_id=project_id,
        enabled=True,
        destination_email=settings.alert_default_destination_email,
        email_enabled=True,
        slack_enabled=bool(settings.alert_slack_webhook_url),
        slack_webhook_url=settings.alert_slack_webhook_url,
        discord_enabled=bool(settings.alert_discord_webhook_url),
        discord_webhook_url=settings.alert_discord_webhook_url,
        webhook_enabled=bool(settings.alert_webhook_url),
        webhook_url=settings.alert_webhook_url,
        error_spike_ratio_threshold=settings.alert_error_spike_ratio_threshold,
        error_spike_min_requests=settings.alert_error_spike_min_requests,
        error_spike_window_minutes=settings.alert_error_spike_window_minutes,
        outage_min_requests=settings.alert_outage_min_requests,
        outage_window_minutes=settings.alert_outage_window_minutes,
        cooldown_minutes=settings.alert_cooldown_minutes,
    )
    session.add(current)
    await session.flush()
    return current
