from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import WebSocket


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

    async def publish_ingest(self, *, message: IngestBroadcastMessage) -> None:
        project_connections = self._project_connections.get(message.project_id)
        if not project_connections:
            return
        payload = message.to_json()
        disconnected: list[WebSocket] = []
        for websocket in project_connections:
            try:
                await websocket.send_text(payload)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.remove_connection(project_id=message.project_id, websocket=websocket)


project_websocket_hub = ProjectWebSocketHub()
