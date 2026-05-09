from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from lumonox_backend.auth import ProjectContext, get_dashboard_auth_session
from lumonox_backend.core.config import get_settings
from lumonox_backend.database import get_session_maker
from lumonox_backend.realtime import project_websocket_hub

router = APIRouter()


@router.websocket("/updates")
async def dashboard_updates(websocket: WebSocket) -> None:
    """Live dashboard ticks + ingest fan-out.

    Authenticate **after** ``accept()`` so failed auth closes an established WebSocket
    (HTTP 101 in access logs) instead of rejecting the upgrade (logged as HTTP 403 by
    Uvicorn/Starlette when ``close`` is sent before ``accept``).
    """
    settings = get_settings()
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
    try:
        while True:
            raw = await websocket.receive_text()
            if raw.strip().lower() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        project_websocket_hub.remove_connection(project_id=context.project_id, websocket=websocket)


@router.websocket("/log-query/stream")
async def dashboard_log_query_stream(websocket: WebSocket) -> None:
    settings = get_settings()
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
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        project_websocket_hub.remove_connection(project_id=context.project_id, websocket=websocket)
