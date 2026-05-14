"""Dashboard WebSocket routes.

Live overview/metrics use ``/dashboard/updates`` when realtime is enabled.

Structured log exploration uses **HTTP only**: ``POST /dashboard/log-query/validate``
plus the shared ``POST /dashboard/query`` batch path. There is no WebSocket stream for
log queries.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from lumonox_backend.auth import ProjectContext, get_dashboard_auth_session
from lumonox_backend.core.config import get_settings
from lumonox_backend.database import get_session_maker
from lumonox_backend.realtime import build_dashboard_snapshot_payload, project_websocket_hub
from lumonox_backend.realtime.dashboard_snapshot_store import dashboard_snapshot_store

router = APIRouter()


@router.websocket("/updates")
async def dashboard_updates(websocket: WebSocket) -> None:
    """Live dashboard ticks + ingest fan-out.

    Authenticate **after** ``accept()`` so failed auth closes an established WebSocket
    (HTTP 101 in access logs) instead of rejecting the upgrade (logged as HTTP 403 by
    Uvicorn/Starlette when ``close`` is sent before ``accept``).
    """
    settings = get_settings()
    if not (settings.dashboard_realtime_enabled and settings.dashboard_realtime_ws_enabled):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Dashboard realtime websocket is disabled",
        )
        return
    await websocket.accept()
    session_maker = get_session_maker()
    async with session_maker() as session:
        auth_session = await get_dashboard_auth_session(
            session=session, settings=settings, request=websocket
        )
        if auth_session is None:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Missing or invalid dashboard session",
            )
            return
        context = ProjectContext(project_id=auth_session.project_id)

    project_websocket_hub.add_connection(project_id=context.project_id, websocket=websocket)
    await websocket.send_text(
        json.dumps({"type": "subscribed", "project_id": str(context.project_id)}),
    )
    if settings.dashboard_realtime_enabled and settings.dashboard_realtime_ws_enabled:
        snapshot = dashboard_snapshot_store.get(context.project_id)
        if snapshot is None:
            snapshot = dashboard_snapshot_store.upsert(
                project_id=context.project_id,
                snapshot_version=0,
                updated_slices=(),
            )
        await websocket.send_text(build_dashboard_snapshot_payload(snapshot))
    try:
        while True:
            raw = await websocket.receive_text()
            if raw.strip().lower() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
            if not (settings.dashboard_realtime_enabled and settings.dashboard_realtime_ws_enabled):
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            message_type = str(payload.get("type") or "").strip().lower()
            if message_type == "dashboard.subscribe":
                snapshot = dashboard_snapshot_store.get(context.project_id)
                if snapshot is not None:
                    await websocket.send_text(build_dashboard_snapshot_payload(snapshot))
                continue
            if message_type == "dashboard.resume":
                try:
                    client_version = int(payload.get("snapshot_version") or 0)
                except (TypeError, ValueError):
                    client_version = 0
                snapshot = dashboard_snapshot_store.get(context.project_id)
                if snapshot is None:
                    continue
                if int(snapshot.snapshot_version) > client_version:
                    await websocket.send_text(build_dashboard_snapshot_payload(snapshot))
    except WebSocketDisconnect:
        pass
    finally:
        project_websocket_hub.remove_connection(project_id=context.project_id, websocket=websocket)
