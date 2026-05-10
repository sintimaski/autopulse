from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from os import getenv
from uuid import UUID

from fastapi import WebSocket

from lumonox_backend.metrics import service_metrics
from lumonox_backend.realtime.dashboard_snapshot_store import (
    ProjectDashboardSnapshot,
    dashboard_snapshot_store,
)

logger = logging.getLogger(__name__)


def _ws_send_timeout_seconds() -> float:
    raw = getenv("LUMONOX_WS_SEND_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return 3.0
    try:
        return max(0.25, min(float(raw.strip()), 60.0))
    except ValueError:
        return 3.0


def _max_delta_queue_per_project() -> int:
    raw = getenv("LUMONOX_DASHBOARD_REALTIME_MAX_DELTA_QUEUE_PER_PROJECT")
    if raw is None or not raw.strip():
        return 32
    try:
        return max(1, min(int(raw.strip()), 4096))
    except ValueError:
        return 32


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
    delta_payload: dict[str, object] | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": "dashboard_update",
                "project_id": str(self.project_id),
                "version": int(self.version),
                "reason": self.reason,
                "updated_slices": list(self.updated_slices),
                "updated_at": self.updated_at.astimezone(UTC).isoformat(),
                "delta_payload": self.delta_payload,
            }
        )


def build_dashboard_snapshot_payload(snapshot: ProjectDashboardSnapshot) -> str:
    return json.dumps(
        {
            "type": "dashboard.snapshot",
            "project_id": str(snapshot.project_id),
            "snapshot_version": int(snapshot.snapshot_version),
            "updated_at": snapshot.updated_at.astimezone(UTC).isoformat(),
            "updated_slices": list(snapshot.updated_slices),
            "window_policy": snapshot.window_policy
            or {
                "default_window_minutes": 60,
                "supported_window_minutes": [15, 60, 240, 1440, 2880, 10080],
            },
            "is_partial": bool(snapshot.is_partial),
            "degraded_reason": snapshot.degraded_reason,
        }
    )


def build_dashboard_delta_payload(message: DashboardUpdateMessage) -> str:
    to_version = int(message.version)
    return json.dumps(
        {
            "type": "dashboard.delta",
            "project_id": str(message.project_id),
            "from_version": max(0, to_version - 1),
            "to_version": to_version,
            "reason": message.reason,
            "updated_slices": list(message.updated_slices),
            "updated_at": message.updated_at.astimezone(UTC).isoformat(),
            "payload": message.delta_payload,
        }
    )


class ProjectWebSocketHub:
    def __init__(self) -> None:
        self._project_connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._project_delta_queues: dict[UUID, deque[DashboardUpdateMessage]] = defaultdict(deque)
        self._project_delta_workers: dict[UUID, asyncio.Task[None]] = {}
        self._delta_worker_lock = asyncio.Lock()

    def add_connection(self, *, project_id: UUID, websocket: WebSocket) -> None:
        self._project_connections[project_id].add(websocket)
        service_metrics.set_value(
            "dashboard.ws.connected_clients",
            sum(len(connections) for connections in self._project_connections.values()),
        )

    def remove_connection(self, *, project_id: UUID, websocket: WebSocket) -> None:
        project_connections = self._project_connections.get(project_id)
        if not project_connections:
            return
        project_connections.discard(websocket)
        if not project_connections:
            self._project_connections.pop(project_id, None)
        service_metrics.set_value(
            "dashboard.ws.connected_clients",
            sum(len(connections) for connections in self._project_connections.values()),
        )

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

    async def _delta_worker(self, project_id: UUID) -> None:
        try:
            while True:
                async with self._delta_worker_lock:
                    queue = self._project_delta_queues.get(project_id)
                    if queue is None or len(queue) == 0:
                        self._project_delta_workers.pop(project_id, None)
                        return
                    message = queue.popleft()
                await self._broadcast_text(
                    project_id=project_id,
                    payload=build_dashboard_delta_payload(message),
                    log_context=f"dashboard.delta:{message.reason}",
                )
                service_metrics.increment("dashboard.ws.publish.delta_total")
                # Keep only latest state if producers outrun consumers.
                async with self._delta_worker_lock:
                    queue = self._project_delta_queues.get(project_id)
                    if queue is None or len(queue) <= 1:
                        continue
                    latest = queue[-1]
                    dropped = max(0, len(queue) - 1)
                    queue.clear()
                    queue.append(latest)
                    if dropped:
                        service_metrics.increment(
                            "dashboard.ws.publish.delta_queue_coalesced_total",
                            amount=dropped,
                        )
        finally:
            async with self._delta_worker_lock:
                worker = self._project_delta_workers.get(project_id)
                if worker is not None and worker.done():
                    self._project_delta_workers.pop(project_id, None)

    async def _enqueue_dashboard_delta(self, message: DashboardUpdateMessage) -> None:
        project_id = message.project_id
        max_depth = _max_delta_queue_per_project()
        should_publish_degraded = False
        created_worker: asyncio.Task[None] | None = None
        async with self._delta_worker_lock:
            queue = self._project_delta_queues[project_id]
            if len(queue) >= max_depth:
                dropped = len(queue)
                queue.clear()
                service_metrics.increment(
                    "dashboard.ws.publish.delta_queue_dropped_total",
                    amount=dropped,
                )
                should_publish_degraded = True
            queue.append(message)
            worker = self._project_delta_workers.get(project_id)
            if worker is None or worker.done():
                created_worker = asyncio.create_task(
                    self._delta_worker(project_id),
                    name=f"dashboard-delta-worker:{project_id}",
                )
                self._project_delta_workers[project_id] = created_worker
        if should_publish_degraded:
            await self._broadcast_text(
                project_id=project_id,
                payload=json.dumps(
                    {
                        "type": "dashboard.degraded",
                        "project_id": str(project_id),
                        "reason": "delta_queue_pressure",
                    }
                ),
                log_context="dashboard.degraded:delta_queue_pressure",
            )
        if created_worker is not None:
            await created_worker

    async def publish_ingest(self, *, message: IngestBroadcastMessage) -> None:
        await self._broadcast_text(
            project_id=message.project_id,
            payload=message.to_json(),
            log_context="ingest",
        )

    async def publish_dashboard_update(self, *, message: DashboardUpdateMessage) -> None:
        dashboard_snapshot_store.upsert(
            project_id=message.project_id,
            snapshot_version=int(message.version),
            updated_slices=tuple(message.updated_slices),
            updated_at=message.updated_at,
        )
        await self._broadcast_text(
            project_id=message.project_id,
            payload=message.to_json(),
            log_context=f"dashboard_update:{message.reason}",
        )
        await self._enqueue_dashboard_delta(message)


project_websocket_hub = ProjectWebSocketHub()
