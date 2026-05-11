"""Dashboard SQL log query API (HTTP only).

Clients validate with ``POST /dashboard/log-query/validate`` and fetch pages with
``POST /dashboard/log-query/execute`` (cursor-based pagination). There is **no** WebSocket
for log streaming; use repeated HTTP execute calls for refresh.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.core.config import get_settings
from lumonox_backend.dashboard.duckdb_queries import build_filters
from lumonox_backend.dashboard.log_query import (
    LOG_QUERY_MAX_LIMIT,
    apply_log_query_filters,
    decode_log_cursor,
    encode_log_cursor,
    parse_log_query,
)
from lumonox_backend.dashboard.params import DEFAULT_WINDOW_MINUTES
from lumonox_backend.dashboard.repositories.project_ui import get_or_create_project_ui_settings
from lumonox_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from lumonox_backend.database import get_db_session
from lumonox_backend.ingestion.exclude_lumonox import append_exclude_lumonox_event_filters
from lumonox_backend.models import Event
from lumonox_backend.schemas import (
    DashboardLogQueryItem,
    DashboardLogQueryPageResponse,
    DashboardLogQueryRequest,
    DashboardLogQueryValidationResponse,
)
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_plane_read_path import resolve_dashboard_read_store
from lumonox_backend.services.event_store import event_store_enabled

router = APIRouter()


@router.post("/log-query/validate", response_model=DashboardLogQueryValidationResponse)
async def validate_dashboard_log_query(
    payload: DashboardLogQueryRequest,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardLogQueryValidationResponse:
    _ = context
    _ = session
    try:
        parsed = parse_log_query(payload.query)
    except HTTPException as exc:
        return DashboardLogQueryValidationResponse(
            valid=False,
            normalized_query=payload.query.strip(),
            error=str(exc.detail),
        )
    return DashboardLogQueryValidationResponse(
        valid=True,
        normalized_query=parsed.normalized_query,
        error=None,
    )


@router.post("/log-query/execute", response_model=DashboardLogQueryPageResponse)
async def execute_dashboard_log_query(
    payload: DashboardLogQueryRequest,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardLogQueryPageResponse:
    server_now = datetime.now(tz=UTC)
    settings = get_settings()
    parsed = parse_log_query(payload.query)
    ui_settings = await get_or_create_project_ui_settings(session, context.project_id)
    max_minutes = max(
        1,
        int(ui_settings.logs_query_max_window_minutes or settings.logs_query_max_window_minutes),
    )
    resolved_from, resolved_to = resolve_time_window(
        payload.from_timestamp,
        payload.to_timestamp,
        min(max_minutes, DEFAULT_WINDOW_MINUTES),
        now_utc=server_now,
    )
    if (resolved_to - resolved_from) > timedelta(minutes=max_minutes):
        resolved_from = resolved_to - timedelta(minutes=max_minutes)

    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
    ]
    append_exclude_lumonox_event_filters(
        filters, exclude_lumonox_traffic=bool(ui_settings.exclude_lumonox_traffic)
    )
    apply_log_query_filters(filters, parsed.where_clauses)
    if event_store_enabled():
        duckdb_filters = build_filters(
            project_id=context.project_id,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            exclude_lumonox_traffic=bool(ui_settings.exclude_lumonox_traffic),
            event_sql_filter=" AND ".join(parsed.where_clauses) if parsed.where_clauses else None,
            http_events_only=False,
        )
        order_by = "id DESC" if parsed.order_by == "id" and parsed.order_desc else None
        if parsed.order_by == "id" and not parsed.order_desc:
            order_by = "id ASC"
        if parsed.order_by == "timestamp":
            order_by = "timestamp DESC, id DESC" if parsed.order_desc else "timestamp ASC, id ASC"
        requested_limit = max(1, min(payload.page_size, parsed.limit, LOG_QUERY_MAX_LIMIT))
        store = await resolve_dashboard_read_store(
            session=session,
            project_id=context.project_id,
            settings=settings,
        )
        cursor = decode_log_cursor(payload.cursor)
        duckdb_filters_effective = duckdb_filters
        if cursor is not None:
            cursor_ts, cursor_id = cursor
            duckdb_filters_effective = replace(
                duckdb_filters,
                log_keyset_timestamp=cursor_ts,
                log_keyset_id=int(cursor_id),
                log_keyset_order="id" if parsed.order_by == "id" else "timestamp",
                log_keyset_desc=parsed.order_desc,
            )
        rows = await run_duckdb_read_sync(
            store.fetch_events,
            duckdb_filters_effective,
            duckdb_read_operation="log_query",
            columns=(
                "id, timestamp, method, path, status_code, latency_ms, "
                "service_name, environment, request_id"
            ),
            order_by=order_by or "timestamp DESC, id DESC",
            limit=requested_limit + 1,
            offset=0,
        )
        selected_rows = rows[:requested_limit]
        has_more = len(rows) > requested_limit
        next_cursor = None
        if has_more and selected_rows:
            last = selected_rows[-1]
            next_cursor = encode_log_cursor(timestamp=last[1], event_id=int(last[0]))
        return DashboardLogQueryPageResponse(
            server_now=server_now,
            query=parsed.normalized_query,
            next_cursor=next_cursor,
            items=[
                DashboardLogQueryItem(
                    id=int(event_id),
                    timestamp=as_utc_datetime(timestamp),
                    method=method,
                    path=path,
                    status_code=int(status_code),
                    latency_ms=float(latency_ms),
                    service_name=service_name,
                    environment=environment,
                    request_id=request_id,
                )
                for (
                    event_id,
                    timestamp,
                    method,
                    path,
                    status_code,
                    latency_ms,
                    service_name,
                    environment,
                    request_id,
                ) in selected_rows
            ],
        )
    cursor = decode_log_cursor(payload.cursor)
    if cursor is not None:
        cursor_ts, cursor_id = cursor
        if parsed.order_by == "id":
            if parsed.order_desc:
                filters.append(Event.id < cursor_id)
            else:
                filters.append(Event.id > cursor_id)
        else:
            if parsed.order_desc:
                filters.append(
                    (Event.timestamp < cursor_ts)
                    | ((Event.timestamp == cursor_ts) & (Event.id < cursor_id))
                )
            else:
                filters.append(
                    (Event.timestamp > cursor_ts)
                    | ((Event.timestamp == cursor_ts) & (Event.id > cursor_id))
                )

    requested_limit = max(1, min(payload.page_size, parsed.limit, LOG_QUERY_MAX_LIMIT))
    order_column = Event.id if parsed.order_by == "id" else Event.timestamp
    direction = order_column.desc() if parsed.order_desc else order_column.asc()
    results = await session.execute(
        select(
            Event.id,
            Event.timestamp,
            Event.method,
            Event.path,
            Event.status_code,
            Event.latency_ms,
            Event.service_name,
            Event.environment,
            Event.request_id,
        )
        .where(*filters)
        .order_by(direction, Event.id.desc() if parsed.order_desc else Event.id.asc())
        .limit(requested_limit + 1)
    )
    orm_rows = results.all()
    orm_has_more = len(orm_rows) > requested_limit
    selected_orm_rows = orm_rows[:requested_limit]
    next_cursor = None
    if orm_has_more and selected_orm_rows:
        last_orm = selected_orm_rows[-1]
        next_cursor = encode_log_cursor(timestamp=last_orm[1], event_id=int(last_orm[0]))
    return DashboardLogQueryPageResponse(
        server_now=server_now,
        query=parsed.normalized_query,
        next_cursor=next_cursor,
        items=[
            DashboardLogQueryItem(
                id=int(event_id),
                timestamp=as_utc_datetime(timestamp),
                method=method,
                path=path,
                status_code=int(status_code),
                latency_ms=float(latency_ms),
                service_name=service_name,
                environment=environment,
                request_id=request_id,
            )
            for (
                event_id,
                timestamp,
                method,
                path,
                status_code,
                latency_ms,
                service_name,
                environment,
                request_id,
            ) in selected_orm_rows
        ],
    )
