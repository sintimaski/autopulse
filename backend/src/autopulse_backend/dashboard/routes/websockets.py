from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_backend.auth import ProjectContext, get_dashboard_auth_session
from autopulse_backend.config import get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.realtime import project_websocket_hub

router = APIRouter()


@router.websocket("/updates")
async def dashboard_updates(websocket: WebSocket) -> None:
    settings = get_settings()
    session_cookie = websocket.cookies.get(settings.dashboard_auth_session_cookie_name)
    if not session_cookie:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing dashboard session"
        )
        return
    session_maker = async_sessionmaker(
        bind=get_engine(), expire_on_commit=False, class_=AsyncSession
    )
    async with session_maker() as session:
        auth_session = await get_dashboard_auth_session(
            session=session, settings=settings, request=websocket
        )
        if auth_session is None:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired dashboard session"
            )
            return
        context = ProjectContext(project_id=auth_session.project_id)

    await websocket.accept()
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
    session_cookie = websocket.cookies.get(settings.dashboard_auth_session_cookie_name)
    if not session_cookie:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing dashboard session"
        )
        return
    session_maker = async_sessionmaker(
        bind=get_engine(), expire_on_commit=False, class_=AsyncSession
    )
    async with session_maker() as session:
        auth_session = await get_dashboard_auth_session(
            session=session, settings=settings, request=websocket
        )
        if auth_session is None:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid or expired dashboard session",
            )
            return
        context = ProjectContext(project_id=auth_session.project_id)
    await websocket.accept()
    project_websocket_hub.add_connection(project_id=context.project_id, websocket=websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        project_websocket_hub.remove_connection(project_id=context.project_id, websocket=websocket)
