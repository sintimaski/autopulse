from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_dashboard_project
from autopulse_backend.config import get_settings
from autopulse_backend.dashboard.log_query import (
    LOG_QUERY_MAX_LIMIT,
    apply_log_query_filters,
    decode_log_cursor,
    encode_log_cursor,
    parse_log_query,
)
from autopulse_backend.dashboard.params import DEFAULT_WINDOW_MINUTES
from autopulse_backend.dashboard.repositories.project_ui import get_or_create_project_ui_settings
from autopulse_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from autopulse_backend.database import get_db_session
from autopulse_backend.ingestion.exclude_autopulse import append_exclude_autopulse_event_filters
from autopulse_backend.models import Event
from autopulse_backend.schemas import (
    DashboardLogQueryItem,
    DashboardLogQueryPageResponse,
    DashboardLogQueryRequest,
    DashboardLogQueryValidationResponse,
)

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
    append_exclude_autopulse_event_filters(
        filters, exclude_autopulse_traffic=bool(ui_settings.exclude_autopulse_traffic)
    )
    apply_log_query_filters(filters, parsed.where_clauses)
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
    rows = list(results)
    has_more = len(rows) > requested_limit
    selected_rows = rows[:requested_limit]
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
