from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.core.config import get_settings
from lumonox_backend.dashboard.duckdb_queries import build_filters
from lumonox_backend.dashboard.params import DEFAULT_WINDOW_MINUTES
from lumonox_backend.dashboard.repositories.project_ui import get_or_create_project_ui_settings
from lumonox_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from lumonox_backend.database import get_db_session
from lumonox_backend.schemas import (
    DashboardTraceDetailResponse,
    DashboardTraceSearchResponse,
    DashboardTraceSpanItem,
    DashboardTraceSummaryItem,
)
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_plane_read_path import resolve_dashboard_read_store
from lumonox_backend.services.event_store import event_store_enabled

router = APIRouter()
_TRACE_ID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


def _optional_upper_method(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    return raw.strip().upper()[:24]


@router.get("/traces/search", response_model=DashboardTraceSearchResponse)
async def search_dashboard_traces(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = Query(default=None),
    to_timestamp: datetime | None = Query(default=None),
    window_minutes: int = Query(default=60, ge=1, le=10_080),
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    environments: str | None = Query(default=None, description="Comma-separated environment names"),
    services: str | None = Query(default=None, description="Comma-separated service names"),
    method: str | None = Query(default=None, description="HTTP method filter, e.g. GET"),
    status_class: int | None = Query(
        default=None, ge=2, le=5, description="Status class 2–5xx (e.g. 5)"
    ),
    path_contains: str | None = Query(default=None, description="Case-insensitive path substring"),
) -> DashboardTraceSearchResponse:
    if not event_store_enabled():
        raise HTTPException(status_code=400, detail="Tracing explorer requires DuckDB event store.")
    server_now = datetime.now(tz=UTC)
    settings = get_settings()
    ui_settings = await get_or_create_project_ui_settings(session, context.project_id)
    max_minutes = max(
        1,
        int(ui_settings.logs_query_max_window_minutes or settings.logs_query_max_window_minutes),
    )
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp,
        to_timestamp,
        min(max_minutes, window_minutes or DEFAULT_WINDOW_MINUTES),
        now_utc=server_now,
    )
    if (resolved_to - resolved_from) > timedelta(minutes=max_minutes):
        resolved_from = resolved_to - timedelta(minutes=max_minutes)

    # status_class is applied as a post-group HAVING filter (see having_clause below) so a
    # trace's span_count / error_count reflect the *whole* trace, not just matching spans.
    # "errors only" then just decides which traces appear, keeping list/detail counts aligned.
    filters = build_filters(
        project_id=context.project_id,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        exclude_lumonox_traffic=bool(ui_settings.exclude_lumonox_traffic),
        http_events_only=False,
        include_received_at_in_time_window=True,
        environments=environments,
        services=services,
        method=_optional_upper_method(method),
        path_contains=path_contains,
    )
    store = await resolve_dashboard_read_store(
        session=session,
        project_id=context.project_id,
        settings=settings,
    )
    safe_q = q.strip().lower()
    search_where = ""
    params: list[object] = []
    if safe_q:
        search_where = (
            "AND (lower(trace_id) LIKE ? OR lower(path) LIKE ? "
            "OR lower(service_name) LIKE ? OR lower(span_name) LIKE ?)"
        )
        like = f"%{safe_q}%"
        params.extend([like, like, like, like])
    having_clause = ""
    if status_class is not None:
        lower_bound = status_class * 100
        upper_bound = lower_bound + 100
        having_clause = (
            "HAVING sum("
            f"CASE WHEN status_code >= {lower_bound} AND status_code < {upper_bound} "
            "THEN 1 ELSE 0 END) > 0"
        )
    query = f"""
        WITH spans AS (
            SELECT
              timestamp,
              service_name,
              path,
              status_code,
              json_extract_string(payload, '$.trace_id') AS trace_id,
              json_extract_string(payload, '$.span_name') AS span_name
            FROM scoped_events
            WHERE json_extract_string(payload, '$.trace_id') IS NOT NULL
        ),
        grouped AS (
            SELECT
              trace_id,
              min(timestamp) AS first_seen,
              max(timestamp) AS last_seen,
              count(*)::BIGINT AS span_count,
              sum(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END)::BIGINT AS error_count,
              string_agg(DISTINCT service_name, ', ') AS services,
              any_value(span_name) AS root_span_name
            FROM spans
            WHERE trace_id IS NOT NULL
            {search_where}
            GROUP BY trace_id
            {having_clause}
        )
        SELECT trace_id, first_seen, last_seen, span_count, error_count, services, root_span_name
        FROM grouped
        ORDER BY last_seen DESC
        LIMIT ?
    """  # nosec B608
    params.append(limit)
    columns, rows = await run_duckdb_read_sync(
        store.query_scoped_events_sql,
        filters,
        query,
        limit,
        params,
        duckdb_read_operation="traces_search",
    )
    _ = columns
    items = [
        DashboardTraceSummaryItem(
            trace_id=str(trace_id),
            first_seen=as_utc_datetime(first_seen),
            last_seen=as_utc_datetime(last_seen),
            span_count=int(span_count),
            error_count=int(error_count),
            services=[s.strip() for s in str(services_csv or "").split(",") if s.strip()],
            root_span_name=str(root_span_name) if root_span_name else None,
        )
        for (
            trace_id,
            first_seen,
            last_seen,
            span_count,
            error_count,
            services_csv,
            root_span_name,
        ) in rows
    ]
    return DashboardTraceSearchResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        project_id=context.project_id,
        total=len(items),
        items=items,
    )


@router.get("/traces/{trace_id}", response_model=DashboardTraceDetailResponse)
async def get_dashboard_trace_detail(
    trace_id: str,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = Query(default=None),
    to_timestamp: datetime | None = Query(default=None),
    window_minutes: int = Query(default=60, ge=1, le=10_080),
) -> DashboardTraceDetailResponse:
    if not event_store_enabled():
        raise HTTPException(status_code=400, detail="Tracing explorer requires DuckDB event store.")
    normalized_trace_id = trace_id.strip().lower()
    if not _TRACE_ID_HEX_RE.match(normalized_trace_id):
        raise HTTPException(status_code=422, detail="trace_id must be a 32-char lowercase hex id")
    server_now = datetime.now(tz=UTC)
    settings = get_settings()
    ui_settings = await get_or_create_project_ui_settings(session, context.project_id)
    max_minutes = max(
        1,
        int(ui_settings.logs_query_max_window_minutes or settings.logs_query_max_window_minutes),
    )
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp,
        to_timestamp,
        min(max_minutes, window_minutes or DEFAULT_WINDOW_MINUTES),
        now_utc=server_now,
    )
    if (resolved_to - resolved_from) > timedelta(minutes=max_minutes):
        resolved_from = resolved_to - timedelta(minutes=max_minutes)
    # Time window only: list filters (service, status, …) must not hide spans in the timeline.
    filters = build_filters(
        project_id=context.project_id,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        exclude_lumonox_traffic=bool(ui_settings.exclude_lumonox_traffic),
        http_events_only=False,
        include_received_at_in_time_window=True,
    )
    store = await resolve_dashboard_read_store(
        session=session,
        project_id=context.project_id,
        settings=settings,
    )
    query = """
        SELECT
          timestamp,
          service_name,
          environment,
          method,
          path,
          status_code,
          latency_ms,
          request_id,
          json_extract_string(payload, '$.trace_id') AS trace_id,
          json_extract_string(payload, '$.span_id') AS span_id,
          json_extract_string(payload, '$.parent_span_id') AS parent_span_id,
          json_extract_string(payload, '$.span_name') AS span_name,
          try_cast(
            json_extract_string(payload, '$.otlp_status_code') AS INTEGER
          ) AS otlp_status_code
        FROM scoped_events
        WHERE lower(json_extract_string(payload, '$.trace_id')) = ?
        ORDER BY timestamp ASC, id ASC
        LIMIT 1000
    """
    _, rows = await run_duckdb_read_sync(
        store.query_scoped_events_sql,
        filters,
        query,
        1000,
        [normalized_trace_id],
        duckdb_read_operation="trace_detail",
    )
    items = [
        DashboardTraceSpanItem(
            timestamp=as_utc_datetime(timestamp),
            service_name=str(service_name),
            environment=str(environment),
            span_name=str(span_name or path),
            path=str(path),
            method=str(method),
            status_code=int(status_code),
            latency_ms=float(latency_ms),
            trace_id=str(trace_id_row),
            span_id=str(span_id) if span_id else None,
            parent_span_id=str(parent_span_id) if parent_span_id else None,
            request_id=str(request_id) if request_id else None,
            otlp_status_code=int(otlp_status_code) if otlp_status_code is not None else None,
        )
        for (
            timestamp,
            service_name,
            environment,
            method,
            path,
            status_code,
            latency_ms,
            request_id,
            trace_id_row,
            span_id,
            parent_span_id,
            span_name,
            otlp_status_code,
        ) in rows
    ]
    first_seen = items[0].timestamp if items else None
    last_seen = items[-1].timestamp if items else None
    error_count = sum(1 for item in items if item.status_code >= 500)
    return DashboardTraceDetailResponse(
        trace_id=normalized_trace_id,
        first_seen=first_seen,
        last_seen=last_seen,
        error_count=error_count,
        items=items,
    )
