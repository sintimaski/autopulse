from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from os import getenv
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _ws_send_timeout_seconds() -> float:
    raw = getenv("LUMONOX_WS_SEND_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return 3.0
    try:
        return max(0.25, min(float(raw.strip()), 60.0))
    except ValueError:
        return 3.0


@dataclass(frozen=True, slots=True)
class IngestBroadcastMessage:
    project_id: UUID
    accepted: int
    received_at: datetime

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": "ingest",
                "project_id": str(self.project_id),
                "accepted": self.accepted,
                "received_at": self.received_at.astimezone(UTC).isoformat(),
            }
        )


@dataclass(frozen=True, slots=True)
class DashboardUpdateMessage:
    project_id: UUID
    version: int
    reason: str
    updated_slices: tuple[str, ...]
    updated_at: datetime

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": "dashboard_update",
                "project_id": str(self.project_id),
                "version": int(self.version),
                "reason": self.reason,
                "updated_slices": list(self.updated_slices),
                "updated_at": self.updated_at.astimezone(UTC).isoformat(),
            }
        )


class ProjectWebSocketHub:
    def __init__(self) -> None:
        self._project_connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    def add_connection(self, *, project_id: UUID, websocket: WebSocket) -> None:
        self._project_connections[project_id].add(websocket)

    def remove_connection(self, *, project_id: UUID, websocket: WebSocket) -> None:
        project_connections = self._project_connections.get(project_id)
        if not project_connections:
            return
        project_connections.discard(websocket)
        if not project_connections:
            self._project_connections.pop(project_id, None)

    def connected_project_ids(self) -> list[UUID]:
        """Projects that currently have at least one dashboard WebSocket connection."""
        return list(self._project_connections.keys())

    async def _broadcast_text(self, *, project_id: UUID, payload: str, log_context: str) -> None:
        """Send the same payload to all dashboard sockets for a project.

        Sends run in parallel with a per-socket timeout so one slow or blocked
        client (browser not reading TCP buffer) cannot stall ingest or the live
        tick loop for other subscribers.
        """
        project_connections = self._project_connections.get(project_id)
        if not project_connections:
            return
        recipients = list(project_connections)
        timeout = _ws_send_timeout_seconds()

        async def _send_one(websocket: WebSocket) -> tuple[WebSocket, bool]:
            try:
                await asyncio.wait_for(websocket.send_text(payload), timeout=timeout)
                return (websocket, True)
            except TimeoutError:
                logger.warning(
                    "websocket_send_timeout",
                    extra={"project_id": str(project_id), "context": log_context},
                )
                return (websocket, False)
            except Exception:
                return (websocket, False)

        results = await asyncio.gather(
            *(_send_one(ws) for ws in recipients),
            return_exceptions=True,
        )
        for item in results:
            if isinstance(item, BaseException):
                logger.debug(
                    "websocket_broadcast_task_failed",
                    exc_info=item,
                    extra={"project_id": str(project_id), "context": log_context},
                )
                continue
            websocket, ok = item
            if not ok:
                self.remove_connection(project_id=project_id, websocket=websocket)

    async def publish_ingest(self, *, message: IngestBroadcastMessage) -> None:
        await self._broadcast_text(
            project_id=message.project_id,
            payload=message.to_json(),
            log_context="ingest",
        )

    async def publish_dashboard_update(self, *, message: DashboardUpdateMessage) -> None:
        await self._broadcast_text(
            project_id=message.project_id,
            payload=message.to_json(),
            log_context=f"dashboard_update:{message.reason}",
        )


project_websocket_hub = ProjectWebSocketHub()
