from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy import text

from lumonox_backend.core.config import Settings
from lumonox_backend.database import get_engine
from lumonox_backend.metrics import service_metrics
from lumonox_backend.realtime import (
    DashboardUpdateMessage,
    IngestBroadcastMessage,
    project_websocket_hub,
)

logger = logging.getLogger(__name__)

_REALTIME_BUS_SENDER_ID = str(uuid4())
_CHANNEL_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def _normalize_pg_url(database_url: str) -> str | None:
    raw = (database_url or "").strip()
    if raw.startswith("postgresql+asyncpg://"):
        return "postgresql://" + raw.removeprefix("postgresql+asyncpg://")
    if raw.startswith("postgresql+psycopg://"):
        return "postgresql://" + raw.removeprefix("postgresql+psycopg://")
    if raw.startswith("postgresql://"):
        return raw
    return None


def _is_postgres_realtime_enabled(settings: Settings) -> bool:
    return settings.dashboard_realtime_bus_backend == "postgres_notify"


def _safe_channel(raw: str) -> str:
    value = (raw or "").strip()
    if _CHANNEL_SAFE_PATTERN.match(value):
        return value
    return "lumonox_dashboard_realtime"


def _parse_iso_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _build_envelope(*, message_type: str, payload_json: str) -> str:
    body = {
        "sender_id": _REALTIME_BUS_SENDER_ID,
        "message_type": message_type,
        "payload_json": payload_json,
    }
    return json.dumps(body, separators=(",", ":"))


async def publish_realtime_ingest(message: IngestBroadcastMessage, *, settings: Settings) -> None:
    await _publish_realtime(
        message_type="ingest",
        payload_json=message.to_json(),
        settings=settings,
    )


async def publish_realtime_dashboard_update(
    message: DashboardUpdateMessage, *, settings: Settings
) -> None:
    await _publish_realtime(
        message_type="dashboard_update",
        payload_json=message.to_json(),
        settings=settings,
    )


async def _publish_realtime(*, message_type: str, payload_json: str, settings: Settings) -> None:
    if not _is_postgres_realtime_enabled(settings):
        return
    pg_url = _normalize_pg_url(settings.database_url)
    if not pg_url:
        service_metrics.increment("dashboard.realtime_bus.publish.skipped_non_postgres")
        return
    envelope = _build_envelope(message_type=message_type, payload_json=payload_json)
    # PostgreSQL NOTIFY payload limit is 8000 bytes.
    if len(envelope.encode("utf-8")) > 7900:
        service_metrics.increment("dashboard.realtime_bus.publish.skipped_payload_too_large")
        logger.warning(
            "dashboard_realtime_bus_payload_too_large",
            extra={
                "message_type": message_type,
                "channel": settings.dashboard_realtime_bus_channel,
            },
        )
        return
    try:
        engine = get_engine(settings.database_url)
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {
                    "channel": _safe_channel(settings.dashboard_realtime_bus_channel),
                    "payload": envelope,
                },
            )
        service_metrics.increment("dashboard.realtime_bus.publish.sent")
        service_metrics.increment(f"dashboard.realtime_bus.publish.sent.{message_type}")
    except Exception:
        service_metrics.increment("dashboard.realtime_bus.publish.failed")
        logger.exception(
            "dashboard_realtime_bus_publish_failed",
            extra={
                "message_type": message_type,
                "channel": _safe_channel(settings.dashboard_realtime_bus_channel),
            },
        )


async def dispatch_realtime_payload(payload: str) -> None:
    service_metrics.increment("dashboard.realtime_bus.receive.total")
    body = json.loads(payload)
    sender_id = str(body.get("sender_id") or "")
    if sender_id == _REALTIME_BUS_SENDER_ID:
        service_metrics.increment("dashboard.realtime_bus.receive.self_ignored")
        return
    message_type = str(body.get("message_type") or "").strip().lower()
    payload_json = str(body.get("payload_json") or "")
    if not payload_json:
        service_metrics.increment("dashboard.realtime_bus.receive.invalid_payload")
        return
    parsed = json.loads(payload_json)
    if message_type == "ingest":
        ingest_msg = IngestBroadcastMessage(
            project_id=UUID(str(parsed["project_id"])),
            accepted=int(parsed["accepted"]),
            received_at=_parse_iso_timestamp(str(parsed["received_at"])),
        )
        await project_websocket_hub.publish_ingest(message=ingest_msg)
        service_metrics.increment("dashboard.realtime_bus.receive.ingest")
        return
    if message_type == "dashboard_update":
        slices = tuple(str(item) for item in parsed.get("updated_slices", []))
        dashboard_msg = DashboardUpdateMessage(
            project_id=UUID(str(parsed["project_id"])),
            version=int(parsed["version"]),
            reason=str(parsed.get("reason") or "remote"),
            updated_slices=slices,
            updated_at=_parse_iso_timestamp(str(parsed["updated_at"])),
        )
        await project_websocket_hub.publish_dashboard_update(message=dashboard_msg)
        service_metrics.increment("dashboard.realtime_bus.receive.dashboard_update")
        return
    service_metrics.increment("dashboard.realtime_bus.receive.unknown_type")


async def run_postgres_realtime_subscriber(*, settings: Settings) -> None:
    if not _is_postgres_realtime_enabled(settings):
        return
    pg_url = _normalize_pg_url(settings.database_url)
    if not pg_url:
        logger.warning("dashboard_realtime_bus_disabled_non_postgres")
        return
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1024)
    connection: asyncpg.Connection | None = None

    def _listener(
        _connection: asyncpg.Connection,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            service_metrics.increment("dashboard.realtime_bus.receive.queue_full")

    try:
        connection = await asyncpg.connect(pg_url)
        channel = _safe_channel(settings.dashboard_realtime_bus_channel)
        await connection.add_listener(channel, _listener)
        await connection.execute(f'LISTEN "{channel}"')
        service_metrics.increment("dashboard.realtime_bus.subscriber.started")
        while True:
            payload = await queue.get()
            try:
                await dispatch_realtime_payload(payload)
            except Exception:
                service_metrics.increment("dashboard.realtime_bus.receive.dispatch_failed")
                logger.exception("dashboard_realtime_bus_dispatch_failed")
    finally:
        if connection is not None:
            with suppress(Exception):
                await connection.remove_listener(
                    _safe_channel(settings.dashboard_realtime_bus_channel), _listener
                )
            with suppress(Exception):
                await connection.close()
