from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from lumonox_backend.realtime import (
    DashboardUpdateMessage,
    IngestBroadcastMessage,
    project_websocket_hub,
)
from lumonox_backend.realtime import bus as realtime_bus


class _FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_text(self, payload: str) -> None:
        self.messages.append(payload)


def _run(coro):
    return asyncio.run(coro)


def test_dispatch_realtime_payload_fans_out_ingest_message() -> None:
    project_id = uuid4()
    ws = _FakeWebSocket()
    project_websocket_hub.add_connection(project_id=project_id, websocket=ws)  # type: ignore[arg-type]
    try:
        envelope = json.dumps(
            {
                "sender_id": "remote-instance",
                "message_type": "ingest",
                "payload_json": IngestBroadcastMessage(
                    project_id=project_id,
                    accepted=2,
                    received_at=datetime.now(tz=UTC),
                ).to_json(),
            }
        )
        _run(realtime_bus.dispatch_realtime_payload(envelope))
        assert ws.messages, "expected websocket fan-out"
        parsed = json.loads(ws.messages[-1])
        assert parsed["type"] == "ingest"
        assert parsed["project_id"] == str(project_id)
    finally:
        project_websocket_hub.remove_connection(project_id=project_id, websocket=ws)  # type: ignore[arg-type]


def test_dispatch_realtime_payload_fans_out_dashboard_update_message() -> None:
    project_id = uuid4()
    ws = _FakeWebSocket()
    project_websocket_hub.add_connection(project_id=project_id, websocket=ws)  # type: ignore[arg-type]
    try:
        envelope = json.dumps(
            {
                "sender_id": "remote-instance",
                "message_type": "dashboard_update",
                "payload_json": DashboardUpdateMessage(
                    project_id=project_id,
                    version=4,
                    reason="ingest",
                    updated_slices=("overview", "errors"),
                    updated_at=datetime.now(tz=UTC),
                ).to_json(),
            }
        )
        _run(realtime_bus.dispatch_realtime_payload(envelope))
        assert ws.messages, "expected websocket fan-out"
        parsed = json.loads(ws.messages[-1])
        assert parsed["type"] == "dashboard_update"
        assert parsed["version"] == 4
    finally:
        project_websocket_hub.remove_connection(project_id=project_id, websocket=ws)  # type: ignore[arg-type]


def test_dispatch_realtime_payload_ignores_same_sender() -> None:
    project_id = uuid4()
    ws = _FakeWebSocket()
    project_websocket_hub.add_connection(project_id=project_id, websocket=ws)  # type: ignore[arg-type]
    try:
        envelope = json.dumps(
            {
                "sender_id": realtime_bus._REALTIME_BUS_SENDER_ID,
                "message_type": "ingest",
                "payload_json": IngestBroadcastMessage(
                    project_id=project_id,
                    accepted=1,
                    received_at=datetime.now(tz=UTC),
                ).to_json(),
            }
        )
        _run(realtime_bus.dispatch_realtime_payload(envelope))
        assert ws.messages == []
    finally:
        project_websocket_hub.remove_connection(project_id=project_id, websocket=ws)  # type: ignore[arg-type]
