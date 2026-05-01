"""Periodic dashboard WebSocket updates while clients are connected."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from uuid import UUID

from autopulse_backend.realtime import DashboardUpdateMessage, project_websocket_hub

logger = logging.getLogger(__name__)


async def run_dashboard_ws_live_tick_loop(*, interval_seconds: float) -> None:
    """Broadcast ``dashboard_update`` on a fixed cadence for projects with open WS clients.

    Uses a monotonic deadline so a slow tick does not add an *extra* full ``interval`` on
    top of work time; when behind, the next tick runs as soon as the previous one finishes.

    ``publish_dashboard_update`` runs in a background task so slow WebSocket ``send_text``
    calls do not delay the next scheduled tick.

    Ingest already pushes updates; this loop fills quiet periods so the UI can refresh
    on a predictable schedule without starving under load.
    """
    if interval_seconds <= 0:
        return
    from autopulse_backend.dashboard.routes.query_bundle import mark_project_dashboard_dirty

    next_wake = time.monotonic()
    while True:
        now = time.monotonic()
        if next_wake > now:
            await asyncio.sleep(next_wake - now)
        tick_started = time.monotonic()
        next_wake = tick_started + interval_seconds
        try:
            project_ids = project_websocket_hub.connected_project_ids()
        except Exception:
            logger.exception("dashboard_ws_tick.list_connections_failed")
            continue
        if not project_ids:
            continue
        stamp = datetime.now(tz=UTC)

        async def _live_tick_publish(project_id: UUID, version: int, *, at: datetime) -> None:
            try:
                await project_websocket_hub.publish_dashboard_update(
                    message=DashboardUpdateMessage(
                        project_id=project_id,
                        version=version,
                        reason="live_tick",
                        updated_slices=("overview", "requests", "errors", "widgets"),
                        updated_at=at,
                    )
                )
            except Exception:
                logger.exception(
                    "dashboard_ws_tick.publish_failed",
                    extra={"project_id": str(project_id)},
                )

        async def _tick_one(project_id: UUID, *, at: datetime) -> None:
            version = await mark_project_dashboard_dirty(project_id)
            asyncio.create_task(_live_tick_publish(project_id, version, at=at))

        results = await asyncio.gather(
            *(_tick_one(pid, at=stamp) for pid in project_ids),
            return_exceptions=True,
        )
        for item in results:
            if isinstance(item, asyncio.CancelledError):
                raise item
            if isinstance(item, BaseException):
                logger.exception(
                    "dashboard_ws_tick.publish_failed",
                    exc_info=item,
                )
