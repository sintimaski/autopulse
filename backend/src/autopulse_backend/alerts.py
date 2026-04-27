from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.config import Settings
from autopulse_backend.exclude_autopulse import (
    append_exclude_autopulse_event_filters,
    resolve_exclude_autopulse_traffic,
)
from autopulse_backend.models import AlertDispatch, Event, Project, ProjectAlertSettings


@dataclass(slots=True)
class AlertSignal:
    project_id: UUID
    alert_type: str
    destination_email: str | None
    triggered_at: datetime
    window_start: datetime
    window_end: datetime
    detail: dict[str, float | int | str]


class AlertSender(Protocol):
    delivery_kind: str

    def send(self, signal: AlertSignal) -> Awaitable[None]: ...


@dataclass(slots=True)
class StubAlertSender:
    delivery_kind: str = "stub"
    sent: list[AlertSignal] = field(default_factory=list)

    async def send(self, signal: AlertSignal) -> None:
        self.sent.append(signal)


@dataclass(slots=True)
class CompositeAlertSender:
    senders: list[AlertSender]
    delivery_kind: str = "composite"

    async def send(self, signal: AlertSignal) -> None:
        for sender in self.senders:
            await sender.send(signal)


@dataclass(slots=True)
class WebhookAlertSender:
    webhook_url: str
    timeout_seconds: float = 3.0
    delivery_kind: str = "webhook"

    async def send(self, signal: AlertSignal) -> None:
        payload = {
            "alert_type": signal.alert_type,
            "project_id": str(signal.project_id),
            "triggered_at": signal.triggered_at.isoformat(),
            "window_start": signal.window_start.isoformat(),
            "window_end": signal.window_end.isoformat(),
            "destination_email": signal.destination_email,
            "detail": signal.detail,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()


def build_alert_sender(settings: Settings) -> AlertSender:
    mode = (settings.alert_sender_mode or "stub").strip().lower()
    if mode == "webhook":
        if settings.alert_webhook_url:
            return WebhookAlertSender(webhook_url=settings.alert_webhook_url)
        return StubAlertSender()
    if mode == "stub":
        return StubAlertSender()
    return StubAlertSender()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _in_cooldown(last_sent_at: datetime | None, cooldown_minutes: int, now: datetime) -> bool:
    if last_sent_at is None:
        return False
    cooldown_ends = _as_utc(last_sent_at) + timedelta(minutes=cooldown_minutes)
    return now < cooldown_ends


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


async def _request_window_counts(
    session: AsyncSession,
    project_id: UUID,
    window_start: datetime,
    window_end: datetime,
) -> tuple[int, int, int]:
    # Include both request and error event rows in the evaluation window.
    # Ingest paths may emit 5xx failures as `type=error`, and excluding them
    # would undercount errors and prevent expected alert dispatches.
    exclude_autopulse_traffic = await resolve_exclude_autopulse_traffic(session, project_id)
    filters = [
        Event.project_id == project_id,
        Event.type.in_(("request", "error")),
        Event.timestamp >= window_start,
        Event.timestamp <= window_end,
    ]
    append_exclude_autopulse_event_filters(
        filters, exclude_autopulse_traffic=exclude_autopulse_traffic
    )
    result = await session.execute(
        select(
            func.count(Event.id),
            func.sum(case((Event.status_code >= 500, 1), else_=0)),
            func.sum(case((Event.status_code < 500, 1), else_=0)),
        ).where(*filters)
    )
    request_count, error_count, success_count = result.one()
    return int(request_count or 0), int(error_count or 0), int(success_count or 0)


def _record_dispatch(
    session: AsyncSession,
    signal: AlertSignal,
    *,
    delivered_via: str,
    detail: dict[str, float | int | str] | None = None,
) -> None:
    payload = detail if detail is not None else signal.detail
    session.add(
        AlertDispatch(
            project_id=signal.project_id,
            alert_type=signal.alert_type,
            destination_email=signal.destination_email,
            delivered_via=delivered_via,
            triggered_at=signal.triggered_at,
            window_start=signal.window_start,
            window_end=signal.window_end,
            detail=payload,
        )
    )


async def evaluate_alerts_once(
    session: AsyncSession,
    settings: Settings,
    sender: AlertSender | None = None,
    *,
    now: datetime | None = None,
) -> int:
    if not settings.alerts_enabled:
        return 0

    resolved_sender = sender or StubAlertSender()
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
        request_count, error_count, _ = await _request_window_counts(
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
            try:
                await resolved_sender.send(signal)
                _record_dispatch(
                    session,
                    signal,
                    delivered_via=getattr(resolved_sender, "delivery_kind", "unknown"),
                )
                alert_settings.last_error_spike_alert_at = resolved_now
                dispatch_count += 1
            except Exception as exc:  # pragma: no cover - defensive fail-silent behavior
                _record_dispatch(
                    session,
                    signal,
                    delivered_via=f"{getattr(resolved_sender, 'delivery_kind', 'unknown')}-failed",
                    detail={**signal.detail, "delivery_error": str(exc)},
                )

        outage_window_start = resolved_now - timedelta(minutes=alert_settings.outage_window_minutes)
        outage_requests, _, outage_success = await _request_window_counts(
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
            try:
                await resolved_sender.send(signal)
                _record_dispatch(
                    session,
                    signal,
                    delivered_via=getattr(resolved_sender, "delivery_kind", "unknown"),
                )
                alert_settings.last_outage_alert_at = resolved_now
                dispatch_count += 1
            except Exception as exc:  # pragma: no cover - defensive fail-silent behavior
                _record_dispatch(
                    session,
                    signal,
                    delivered_via=f"{getattr(resolved_sender, 'delivery_kind', 'unknown')}-failed",
                    detail={**signal.detail, "delivery_error": str(exc)},
                )

    await session.commit()
    return dispatch_count
