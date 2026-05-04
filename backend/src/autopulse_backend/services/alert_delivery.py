from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import httpx

from autopulse_backend.core.config import Settings


@dataclass(slots=True)
class AlertSignal:
    project_id: UUID
    alert_type: str
    destination_email: str | None
    triggered_at: datetime
    window_start: datetime
    window_end: datetime
    detail: dict[str, float | int | str]


@dataclass(slots=True)
class AlertDeliveryResult:
    status: str
    delivered_via: str
    reason_code: str | None = None
    attempt_count: int = 1
    delivered_at: datetime | None = None
    provider_message_id: str | None = None
    detail: dict[str, float | int | str] | None = None


class AlertSender(Protocol):
    delivery_kind: str

    def send(self, signal: AlertSignal) -> Awaitable[AlertDeliveryResult]: ...


@dataclass(slots=True)
class StubAlertSender:
    delivery_kind: str = "stub"
    sent: list[AlertSignal] = field(default_factory=list)

    async def send(self, signal: AlertSignal) -> AlertDeliveryResult:
        self.sent.append(signal)
        return AlertDeliveryResult(
            status="sent",
            delivered_via=self.delivery_kind,
            delivered_at=_as_utc(datetime.now(tz=UTC)),
        )


@dataclass(slots=True)
class CompositeAlertSender:
    senders: list[AlertSender]
    delivery_kind: str = "composite"

    async def send(self, signal: AlertSignal) -> AlertDeliveryResult:
        delivered_via_parts: list[str] = []
        provider_message_ids: list[str] = []
        total_attempts = 0
        failure_reason: str | None = None
        failed = False
        sent_at: datetime | None = None
        for sender in self.senders:
            result = await sender.send(signal)
            delivered_via_parts.append(result.delivered_via)
            total_attempts += max(1, result.attempt_count)
            if result.provider_message_id:
                provider_message_ids.append(result.provider_message_id)
            if result.delivered_at is not None:
                sent_at = result.delivered_at
            if result.status != "sent":
                failed = True
                failure_reason = failure_reason or result.reason_code or "unknown"
        return AlertDeliveryResult(
            status="failed" if failed else "sent",
            delivered_via="composite",
            reason_code=failure_reason,
            attempt_count=max(1, total_attempts),
            delivered_at=sent_at,
            provider_message_id=",".join(provider_message_ids) or None,
            detail={"channels": ",".join(delivered_via_parts)},
        )


@dataclass(slots=True)
class WebhookAlertSender:
    webhook_url: str
    timeout_seconds: float = 3.0
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    delivery_kind: str = "webhook"

    async def send(self, signal: AlertSignal) -> AlertDeliveryResult:
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
            for attempt in range(1, max(1, self.max_attempts) + 1):
                try:
                    response = await client.post(self.webhook_url, json=payload)
                    response.raise_for_status()
                    return AlertDeliveryResult(
                        status="sent",
                        delivered_via=self.delivery_kind,
                        attempt_count=attempt,
                        delivered_at=_as_utc(datetime.now(tz=UTC)),
                        provider_message_id=response.headers.get("x-request-id"),
                    )
                except Exception as exc:
                    if attempt >= self.max_attempts:
                        return AlertDeliveryResult(
                            status="failed",
                            delivered_via=self.delivery_kind,
                            reason_code=_reason_code_for_exception(exc),
                            attempt_count=attempt,
                            detail={"delivery_error": str(exc)},
                        )
                    await asyncio.sleep(self.initial_backoff_seconds * attempt)
        return AlertDeliveryResult(
            status="failed",
            delivered_via=self.delivery_kind,
            reason_code="timeout",
            attempt_count=max(1, self.max_attempts),
        )


@dataclass(slots=True)
class EmailAlertSender:
    provider: str
    api_key: str | None = None
    from_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_username: str | None = None
    smtp_password: str | None = None
    file_outbox_dir: str | None = None
    timeout_seconds: float = 3.0
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    delivery_kind: str = "email"

    async def send(self, signal: AlertSignal) -> AlertDeliveryResult:
        destination = (signal.destination_email or "").strip()
        if not destination:
            return AlertDeliveryResult(
                status="skipped",
                delivered_via=self.delivery_kind,
                reason_code="missing_destination",
                attempt_count=1,
            )
        provider = self.provider.strip().lower()
        if provider in {"file", "outbox"}:
            return await self._send_file(destination, signal)
        if provider == "sendmail":
            return await self._send_sendmail(destination, signal)
        if provider in {"smtp", "smtp_localhost"}:
            return await self._send_smtp(destination, signal)
        if provider == "resend":
            url = "https://api.resend.com/emails"
            if not self.api_key:
                return AlertDeliveryResult(
                    status="failed",
                    delivered_via=self.delivery_kind,
                    reason_code="missing_api_key",
                    attempt_count=1,
                )
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "from": self.from_email or "autopulse@localhost",
                "to": [destination],
                "subject": f"[AutoPulse] {signal.alert_type} for project {signal.project_id}",
                "text": _format_alert_text(signal),
            }
        elif provider == "postmark":
            url = "https://api.postmarkapp.com/email"
            if not self.api_key:
                return AlertDeliveryResult(
                    status="failed",
                    delivered_via=self.delivery_kind,
                    reason_code="missing_api_key",
                    attempt_count=1,
                )
            headers = {"X-Postmark-Server-Token": self.api_key}
            payload = {
                "From": self.from_email or "autopulse@localhost",
                "To": destination,
                "Subject": f"[AutoPulse] {signal.alert_type} for project {signal.project_id}",
                "TextBody": _format_alert_text(signal),
            }
        else:
            return AlertDeliveryResult(
                status="failed",
                delivered_via=self.delivery_kind,
                reason_code="unknown_provider",
                attempt_count=1,
            )
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(1, max(1, self.max_attempts) + 1):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    provider_message_id = _extract_provider_message_id(provider, response)
                    return AlertDeliveryResult(
                        status="sent",
                        delivered_via=self.delivery_kind,
                        attempt_count=attempt,
                        delivered_at=_as_utc(datetime.now(tz=UTC)),
                        provider_message_id=provider_message_id,
                    )
                except Exception as exc:
                    if attempt >= self.max_attempts:
                        return AlertDeliveryResult(
                            status="failed",
                            delivered_via=self.delivery_kind,
                            reason_code=_reason_code_for_exception(exc),
                            attempt_count=attempt,
                            detail={"delivery_error": str(exc), "provider": provider},
                        )
                    await asyncio.sleep(self.initial_backoff_seconds * attempt)
        return AlertDeliveryResult(
            status="failed",
            delivered_via=self.delivery_kind,
            reason_code="timeout",
            attempt_count=max(1, self.max_attempts),
        )

    async def _send_file(self, destination: str, signal: AlertSignal) -> AlertDeliveryResult:
        message = _build_email_message(self.from_email, destination, signal)
        outbox_dir = Path(self.file_outbox_dir or "./.autopulse/emails").resolve()
        try:
            outbox_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return AlertDeliveryResult(
                status="failed",
                delivered_via=self.delivery_kind,
                reason_code="outbox_unwritable",
                attempt_count=1,
                detail={"delivery_error": str(exc), "outbox_dir": str(outbox_dir)},
            )
        filename = (
            f"{_safe_slug(signal.alert_type)}-"
            f"{signal.project_id}-"
            f"{signal.triggered_at.strftime('%Y%m%dT%H%M%SZ')}-"
            f"{uuid.uuid4().hex}.eml"
        )
        path = outbox_dir / filename
        try:
            await asyncio.to_thread(path.write_bytes, message.as_bytes())
            return AlertDeliveryResult(
                status="sent",
                delivered_via=self.delivery_kind,
                attempt_count=1,
                delivered_at=_as_utc(datetime.now(tz=UTC)),
                provider_message_id=message.get("Message-Id"),
                detail={"outbox_path": str(path)},
            )
        except Exception as exc:
            return AlertDeliveryResult(
                status="failed",
                delivered_via=self.delivery_kind,
                reason_code="outbox_write_failed",
                attempt_count=1,
                detail={"delivery_error": str(exc), "outbox_path": str(path)},
            )

    async def _send_sendmail(self, destination: str, signal: AlertSignal) -> AlertDeliveryResult:
        message = _build_email_message(self.from_email, destination, signal)
        sendmail_path = os.getenv("ALERT_SENDMAIL_PATH", "/usr/sbin/sendmail")
        args = [sendmail_path, "-t", "-i"]
        for attempt in range(1, max(1, self.max_attempts) + 1):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate(input=message.as_bytes())
                if proc.returncode == 0:
                    return AlertDeliveryResult(
                        status="sent",
                        delivered_via=self.delivery_kind,
                        attempt_count=attempt,
                        delivered_at=_as_utc(datetime.now(tz=UTC)),
                        provider_message_id=message.get("Message-Id"),
                    )
                error_text = (stderr or stdout or b"").decode(errors="replace").strip()
                raise RuntimeError(error_text or f"sendmail exited with {proc.returncode}")
            except FileNotFoundError as exc:
                return AlertDeliveryResult(
                    status="failed",
                    delivered_via=self.delivery_kind,
                    reason_code="sendmail_missing",
                    attempt_count=attempt,
                    detail={"delivery_error": str(exc), "sendmail_path": sendmail_path},
                )
            except Exception as exc:
                if attempt >= self.max_attempts:
                    return AlertDeliveryResult(
                        status="failed",
                        delivered_via=self.delivery_kind,
                        reason_code="sendmail_failed",
                        attempt_count=attempt,
                        detail={"delivery_error": str(exc), "sendmail_path": sendmail_path},
                    )
                await asyncio.sleep(self.initial_backoff_seconds * attempt)
        return AlertDeliveryResult(
            status="failed",
            delivered_via=self.delivery_kind,
            reason_code="sendmail_failed",
            attempt_count=max(1, self.max_attempts),
        )

    async def _send_smtp(self, destination: str, signal: AlertSignal) -> AlertDeliveryResult:
        # Uses stdlib smtplib (blocking) off the event loop.
        message = _build_email_message(self.from_email, destination, signal)
        host = (self.smtp_host or "127.0.0.1").strip() or "127.0.0.1"
        port = int(self.smtp_port or 25)

        def _sync_send() -> None:
            import smtplib

            timeout = float(self.timeout_seconds)
            with smtplib.SMTP(host=host, port=port, timeout=timeout) as client:
                client.ehlo()
                if self.smtp_use_tls:
                    client.starttls()
                    client.ehlo()
                if self.smtp_username and self.smtp_password:
                    client.login(self.smtp_username, self.smtp_password)
                client.send_message(message)

        for attempt in range(1, max(1, self.max_attempts) + 1):
            try:
                await asyncio.to_thread(_sync_send)
                return AlertDeliveryResult(
                    status="sent",
                    delivered_via=self.delivery_kind,
                    attempt_count=attempt,
                    delivered_at=_as_utc(datetime.now(tz=UTC)),
                    provider_message_id=message.get("Message-Id"),
                    detail={"smtp_host": host, "smtp_port": port},
                )
            except Exception as exc:
                if attempt >= self.max_attempts:
                    return AlertDeliveryResult(
                        status="failed",
                        delivered_via=self.delivery_kind,
                        reason_code="smtp_failed",
                        attempt_count=attempt,
                        detail={
                            "delivery_error": str(exc),
                            "smtp_host": host,
                            "smtp_port": port,
                        },
                    )
                await asyncio.sleep(self.initial_backoff_seconds * attempt)
        return AlertDeliveryResult(
            status="failed",
            delivered_via=self.delivery_kind,
            reason_code="smtp_failed",
            attempt_count=max(1, self.max_attempts),
        )


@dataclass(slots=True)
class SlackWebhookAlertSender(WebhookAlertSender):
    delivery_kind: str = "slack"

    async def send(self, signal: AlertSignal) -> AlertDeliveryResult:
        payload = {"text": _format_alert_text(signal)}
        return await _send_webhook_payload(
            self.webhook_url,
            payload,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            initial_backoff_seconds=self.initial_backoff_seconds,
            delivery_kind=self.delivery_kind,
        )


@dataclass(slots=True)
class DiscordWebhookAlertSender(WebhookAlertSender):
    delivery_kind: str = "discord"

    async def send(self, signal: AlertSignal) -> AlertDeliveryResult:
        payload = {"content": _format_alert_text(signal)}
        return await _send_webhook_payload(
            self.webhook_url,
            payload,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
            initial_backoff_seconds=self.initial_backoff_seconds,
            delivery_kind=self.delivery_kind,
        )


async def _send_webhook_payload(
    webhook_url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    max_attempts: int,
    initial_backoff_seconds: float,
    delivery_kind: str,
) -> AlertDeliveryResult:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for attempt in range(1, max(1, max_attempts) + 1):
            try:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                return AlertDeliveryResult(
                    status="sent",
                    delivered_via=delivery_kind,
                    attempt_count=attempt,
                    delivered_at=_as_utc(datetime.now(tz=UTC)),
                    provider_message_id=response.headers.get("x-request-id"),
                )
            except Exception as exc:
                if attempt >= max_attempts:
                    return AlertDeliveryResult(
                        status="failed",
                        delivered_via=delivery_kind,
                        reason_code=_reason_code_for_exception(exc),
                        attempt_count=attempt,
                        detail={"delivery_error": str(exc)},
                    )
                await asyncio.sleep(initial_backoff_seconds * attempt)
    return AlertDeliveryResult(
        status="failed",
        delivered_via=delivery_kind,
        reason_code="timeout",
        attempt_count=max(1, max_attempts),
    )


def build_alert_sender(settings: Settings) -> AlertSender:
    mode = (settings.alert_sender_mode or "stub").strip().lower()
    senders: list[AlertSender] = []
    if mode in {"email", "composite"}:
        if settings.alert_email_provider in {"file", "outbox"}:
            senders.append(
                EmailAlertSender(
                    provider=settings.alert_email_provider,
                    from_email=settings.alert_email_from,
                    file_outbox_dir=getattr(settings, "alert_email_file_outbox_dir", None),
                )
            )
        elif settings.alert_email_provider == "sendmail":
            senders.append(
                EmailAlertSender(
                    provider=settings.alert_email_provider,
                    from_email=settings.alert_email_from,
                    max_attempts=3,
                )
            )
        elif settings.alert_email_provider in {"smtp", "smtp_localhost"}:
            senders.append(
                EmailAlertSender(
                    provider=settings.alert_email_provider,
                    from_email=settings.alert_email_from,
                    smtp_host=getattr(settings, "alert_email_smtp_host", None),
                    smtp_port=getattr(settings, "alert_email_smtp_port", 25),
                    smtp_use_tls=getattr(settings, "alert_email_smtp_use_tls", False),
                    smtp_username=getattr(settings, "alert_email_smtp_username", None),
                    smtp_password=getattr(settings, "alert_email_smtp_password", None),
                )
            )
        elif settings.alert_email_api_key and settings.alert_email_from:
            senders.append(
                EmailAlertSender(
                    provider=settings.alert_email_provider,
                    api_key=settings.alert_email_api_key,
                    from_email=settings.alert_email_from,
                )
            )
        elif mode == "email":
            return StubAlertSender()
    if mode in {"webhook", "composite"} and settings.alert_webhook_url:
        senders.append(WebhookAlertSender(webhook_url=settings.alert_webhook_url))
    if mode in {"slack", "composite"}:
        if settings.alert_slack_webhook_url:
            senders.append(SlackWebhookAlertSender(webhook_url=settings.alert_slack_webhook_url))
        elif mode == "slack":
            return StubAlertSender()
    if mode in {"discord", "composite"}:
        if settings.alert_discord_webhook_url:
            senders.append(
                DiscordWebhookAlertSender(webhook_url=settings.alert_discord_webhook_url)
            )
        elif mode == "discord":
            return StubAlertSender()
    if mode == "webhook" and settings.alert_webhook_url and not senders:
        senders.append(WebhookAlertSender(webhook_url=settings.alert_webhook_url))
    if mode == "stub":
        return StubAlertSender()
    if len(senders) == 1:
        return senders[0]
    if len(senders) > 1:
        return CompositeAlertSender(senders=senders)
    return StubAlertSender()


def _extract_provider_message_id(provider: str, response: httpx.Response) -> str | None:
    if provider == "resend":
        try:
            payload = response.json()
            if isinstance(payload, dict):
                value = payload.get("id")
                if isinstance(value, str):
                    return value
        except ValueError:
            return None
    if provider == "postmark":
        try:
            payload = response.json()
            if isinstance(payload, dict):
                value = payload.get("MessageID")
                if isinstance(value, str):
                    return value
        except ValueError:
            return None
    return cast(str | None, response.headers.get("x-request-id"))


def _format_alert_text(signal: AlertSignal) -> str:
    if signal.alert_type == "dashboard_magic_link":
        detail = signal.detail
        magic_link = str(detail.get("magic_link", "")).strip()
        expires_at = str(detail.get("expires_at", "")).strip()
        email = str(detail.get("email", signal.destination_email or "")).strip()
        link_value = ""
        if "token=" in magic_link:
            link_value = magic_link.split("token=", 1)[1]
        return (
            "AutoPulse dashboard sign-in link\n"
            f"email: {email}\n"
            f"expires_at: {expires_at}\n"
            "magic_link:\n"
            f"{magic_link}\n"
            "token:\n"
            f"{link_value}"
        )
    return (
        f"AutoPulse alert: {signal.alert_type}\n"
        f"project_id: {signal.project_id}\n"
        f"triggered_at: {signal.triggered_at.isoformat()}\n"
        f"window_start: {signal.window_start.isoformat()}\n"
        f"window_end: {signal.window_end.isoformat()}\n"
        f"detail: {signal.detail}"
    )


def _build_email_message(
    from_email: str | None, to_email: str, signal: AlertSignal
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = (from_email or "autopulse@localhost").strip() or "autopulse@localhost"
    msg["To"] = to_email
    msg["Subject"] = f"[AutoPulse] {signal.alert_type} for project {signal.project_id}"
    msg["Date"] = formatdate(localtime=False)
    msg["Message-Id"] = make_msgid(domain="autopulse.local")
    msg.set_content(_format_alert_text(signal))
    return msg


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned[:40] or "alert"


def _reason_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return "rate_limited"
        if 400 <= status < 500:
            return "provider_rejected"
        if status >= 500:
            return "provider_unavailable"
    if isinstance(exc, httpx.HTTPError):
        return "network_error"
    return "unknown"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
