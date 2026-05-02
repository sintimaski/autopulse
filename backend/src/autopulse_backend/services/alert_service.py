from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.config import Settings
from autopulse_backend.models import Project
from autopulse_backend.repositories.alert_dispatches import record_alert_dispatch
from autopulse_backend.repositories.alert_settings import get_or_create_project_alert_settings
from autopulse_backend.repositories.events import request_window_counts
from autopulse_backend.services.alert_delivery import (
    AlertDeliveryResult,
    AlertSender,
    AlertSignal,
    CompositeAlertSender,
    DiscordWebhookAlertSender,
    EmailAlertSender,
    SlackWebhookAlertSender,
    StubAlertSender,
    WebhookAlertSender,
    _as_utc,
    build_alert_sender,
)

__all__ = [
    "AlertDeliveryResult",
    "AlertSender",
    "AlertSignal",
    "CompositeAlertSender",
    "DiscordWebhookAlertSender",
    "EmailAlertSender",
    "SlackWebhookAlertSender",
    "StubAlertSender",
    "WebhookAlertSender",
    "build_alert_sender",
    "evaluate_alerts_once",
]


def _in_cooldown(last_sent_at: datetime | None, cooldown_minutes: int, now: datetime) -> bool:
    if last_sent_at is None:
        return False
    cooldown_ends = _as_utc(last_sent_at) + timedelta(minutes=cooldown_minutes)
    return now < cooldown_ends


async def evaluate_alerts_once(
    session: AsyncSession,
    settings: Settings,
    sender: AlertSender | None = None,
    *,
    now: datetime | None = None,
) -> int:
    if not settings.alerts_enabled:
        return 0

    resolved_sender = sender or build_alert_sender(settings)
    resolved_now = _as_utc(now or datetime.now(tz=UTC))
    dispatch_count = 0

    project_ids = list((await session.scalars(select(Project.id))).all())
    for project_id in project_ids:
        alert_settings = await get_or_create_project_alert_settings(session, project_id, settings)
        if not alert_settings.enabled:
            continue

        spike_window_start = resolved_now - timedelta(
            minutes=alert_settings.error_spike_window_minutes
        )
        request_count, error_count, _ = await request_window_counts(
            session,
            project_id,
            spike_window_start,
            resolved_now,
        )
        error_rate = float(error_count / request_count) if request_count > 0 else 0.0
        should_trigger_spike = (
            request_count >= alert_settings.error_spike_min_requests
            and error_rate >= alert_settings.error_spike_ratio_threshold
            and not _in_cooldown(
                alert_settings.last_error_spike_alert_at,
                alert_settings.cooldown_minutes,
                resolved_now,
            )
        )
        if should_trigger_spike:
            signal = AlertSignal(
                project_id=project_id,
                alert_type="error_spike",
                destination_email=alert_settings.destination_email,
                triggered_at=resolved_now,
                window_start=spike_window_start,
                window_end=resolved_now,
                detail={
                    "request_count": request_count,
                    "error_count": error_count,
                    "error_rate": round(error_rate, 4),
                    "threshold": round(alert_settings.error_spike_ratio_threshold, 4),
                },
            )
            dispatch_result = await resolved_sender.send(signal)
            if dispatch_result.status == "sent":
                alert_settings.last_error_spike_alert_at = resolved_now
                dispatch_count += 1
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

        outage_window_start = resolved_now - timedelta(minutes=alert_settings.outage_window_minutes)
        outage_requests, _, outage_success = await request_window_counts(
            session,
            project_id,
            outage_window_start,
            resolved_now,
        )
        should_trigger_outage = (
            outage_requests >= alert_settings.outage_min_requests
            and outage_success == 0
            and not _in_cooldown(
                alert_settings.last_outage_alert_at,
                alert_settings.cooldown_minutes,
                resolved_now,
            )
        )
        if should_trigger_outage:
            signal = AlertSignal(
                project_id=project_id,
                alert_type="possible_outage",
                destination_email=alert_settings.destination_email,
                triggered_at=resolved_now,
                window_start=outage_window_start,
                window_end=resolved_now,
                detail={
                    "request_count": outage_requests,
                    "success_count": outage_success,
                    "min_requests_threshold": alert_settings.outage_min_requests,
                },
            )
            dispatch_result = await resolved_sender.send(signal)
            if dispatch_result.status == "sent":
                alert_settings.last_outage_alert_at = resolved_now
                dispatch_count += 1
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
    return dispatch_count
