from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from io import StringIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.dashboard.duckdb_queries import build_filters, request_items
from lumonox_backend.dashboard.event_scope import http_scoped_event_types_clause
from lumonox_backend.dashboard.log_query import append_event_sql_filters
from lumonox_backend.dashboard.messages import dashboard_request_log_message
from lumonox_backend.dashboard.params import (
    CORRELATION_REQUEST_ID_QUERY,
    ENVIRONMENTS_QUERY,
    EVENT_SQL_FILTER_QUERY,
    FROM_TIMESTAMP_QUERY,
    LATENCY_MAX_MS_QUERY,
    LATENCY_MIN_MS_QUERY,
    LIMIT_QUERY,
    METHOD_QUERY,
    OFFSET_QUERY,
    PATH_QUERY,
    REQUESTS_FOCUS_QUERY,
    SERVICES_QUERY,
    STATUS_CLASS_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
    DashboardRequestsFocus,
)
from lumonox_backend.dashboard.parsing import split_csv_values
from lumonox_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from lumonox_backend.database import get_db_session
from lumonox_backend.ingestion.exclude_lumonox import (
    append_exclude_lumonox_event_filters,
    resolve_exclude_lumonox_traffic,
)
from lumonox_backend.models import Event
from lumonox_backend.schemas import DashboardRequestItem, DashboardRequestsResponse
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_plane_read_path import resolve_dashboard_read_store
from lumonox_backend.services.event_store import event_store_enabled

router = APIRouter()

_EXPORT_WINDOW_MAX = 5000
_EXPORT_LOG_MESSAGE_CSV_MAX = 2000

_CSV_FIELDS: tuple[str, ...] = (
    "timestamp",
    "method",
    "path",
    "status_code",
    "latency_ms",
    "service_name",
    "environment",
    "request_id",
    "event_id",
    "event_kind",
    "received_at",
    "sdk_version",
    "trace_id",
    "span_id",
    "log_message",
)


def _payload_trace_ids(payload: object) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None

    def _norm(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    trace = _norm(payload.get("trace_id")) or _norm(payload.get("traceId"))
    span = _norm(payload.get("span_id")) or _norm(payload.get("spanId"))
    return trace, span


async def fetch_dashboard_requests(
    *,
    session: AsyncSession,
    context: ProjectContext,
    server_now: datetime,
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
    window_minutes: int,
    method: str | None,
    status_class: int | None,
    focus: DashboardRequestsFocus | None,
    path_contains: str | None,
    environments: str | None,
    services: str | None,
    min_latency_ms: float | None,
    max_latency_ms: float | None,
    limit: int,
    offset: int,
    event_sql_filter: str | None,
    correlation_request_id: str | None,
) -> DashboardRequestsResponse:
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    effective_status_class = status_class
    if effective_status_class is None and focus == DashboardRequestsFocus.errors:
        effective_status_class = 5
    exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, context.project_id)
    correlation_norm = str(correlation_request_id or "").strip()[:128] or None
    type_clause = (
        Event.type.in_(("request", "error", "job"))
        if correlation_norm
        else http_scoped_event_types_clause()
    )
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        type_clause,
    ]
    if correlation_norm:
        filters.append(Event.request_id == correlation_norm)
    append_exclude_lumonox_event_filters(filters, exclude_lumonox_traffic=exclude_lumonox_traffic)
    if method:
        filters.append(Event.method == method.upper())
    if effective_status_class is not None:
        lower = effective_status_class * 100
        filters.extend([Event.status_code >= lower, Event.status_code < lower + 100])
    if path_contains:
        lowered = path_contains.strip().lower()
        if lowered:
            filters.append(func.lower(Event.path).contains(lowered))
    if env_values := split_csv_values(environments):
        filters.append(Event.environment.in_(env_values))
    if service_values := split_csv_values(services):
        filters.append(Event.service_name.in_(service_values))
    if min_latency_ms is not None:
        filters.append(Event.latency_ms >= min_latency_ms)
    if max_latency_ms is not None:
        filters.append(Event.latency_ms <= max_latency_ms)
    append_event_sql_filters(filters, event_sql_filter)
    if event_store_enabled():
        read_store = await resolve_dashboard_read_store(
            session=session,
            project_id=context.project_id,
        )
        duckdb_filters = build_filters(
            project_id=context.project_id,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            method=method,
            status_class=effective_status_class,
            path_contains=path_contains,
            environments=environments,
            services=services,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            exclude_lumonox_traffic=exclude_lumonox_traffic,
            event_sql_filter=event_sql_filter,
            http_events_only=True,
            correlation_request_id=correlation_norm,
        )
        total, items = await run_duckdb_read_sync(
            request_items,
            duckdb_filters,
            limit=limit,
            offset=offset,
            store=read_store,
            duckdb_read_operation="requests",
        )
        return DashboardRequestsResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            total=total,
            limit=limit,
            offset=offset,
            items=items,
        )

    total_query = select(func.count(Event.id)).where(*filters)
    total_result = await session.execute(total_query)
    total = int(total_result.scalar_one())

    requests_query = (
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
            Event.type,
            Event.received_at,
            Event.sdk_version,
            Event.payload,
        )
        .where(*filters)
        .order_by(Event.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    requests_result = await session.execute(requests_query)
    items = []
    for (
        event_id,
        ts,
        event_method,
        path,
        status_code,
        latency_ms,
        service_name,
        environment,
        request_id,
        event_type,
        received_at,
        sdk_version,
        payload,
    ) in requests_result:
        trace_id, span_id = _payload_trace_ids(payload)
        items.append(
            DashboardRequestItem(
                timestamp=as_utc_datetime(ts),
                method=event_method,
                path=path,
                status_code=status_code,
                latency_ms=latency_ms,
                service_name=service_name,
                environment=environment,
                request_id=request_id,
                log_message=dashboard_request_log_message(event_type, payload),
                event_id=int(event_id),
                received_at=as_utc_datetime(received_at),
                sdk_version=str(sdk_version) if sdk_version else None,
                event_kind=str(event_type) if event_type else None,
                trace_id=trace_id,
                span_id=span_id,
            )
        )
    return DashboardRequestsResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


def _csv_cell(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


@router.get("/requests", response_model=DashboardRequestsResponse)
async def get_dashboard_requests(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    method: str | None = METHOD_QUERY,
    status_class: int | None = STATUS_CLASS_QUERY,
    focus: DashboardRequestsFocus | None = REQUESTS_FOCUS_QUERY,
    path_contains: str | None = PATH_QUERY,
    environments: str | None = ENVIRONMENTS_QUERY,
    services: str | None = SERVICES_QUERY,
    min_latency_ms: float | None = LATENCY_MIN_MS_QUERY,
    max_latency_ms: float | None = LATENCY_MAX_MS_QUERY,
    limit: int = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
    correlation_request_id: str | None = CORRELATION_REQUEST_ID_QUERY,
) -> DashboardRequestsResponse:
    server_now = datetime.now(tz=UTC)
    return await fetch_dashboard_requests(
        session=session,
        context=context,
        server_now=server_now,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        window_minutes=window_minutes,
        method=method,
        status_class=status_class,
        focus=focus,
        path_contains=path_contains,
        environments=environments,
        services=services,
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
        limit=limit,
        offset=offset,
        event_sql_filter=event_sql_filter,
        correlation_request_id=correlation_request_id,
    )


@router.get("/requests/export")
async def export_dashboard_requests(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    method: str | None = METHOD_QUERY,
    status_class: int | None = STATUS_CLASS_QUERY,
    focus: DashboardRequestsFocus | None = REQUESTS_FOCUS_QUERY,
    path_contains: str | None = PATH_QUERY,
    environments: str | None = ENVIRONMENTS_QUERY,
    services: str | None = SERVICES_QUERY,
    min_latency_ms: float | None = LATENCY_MIN_MS_QUERY,
    max_latency_ms: float | None = LATENCY_MAX_MS_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
    correlation_request_id: str | None = CORRELATION_REQUEST_ID_QUERY,
    export_format: Literal["csv", "json"] = Query(default="csv", alias="format"),
    export_limit: int = Query(default=500, ge=1, le=2000, alias="export_limit"),
    export_offset: int = Query(default=0, ge=0, le=50_000, alias="export_offset"),
) -> Response:
    if export_offset + export_limit > _EXPORT_WINDOW_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"export_offset + export_limit must be <= {_EXPORT_WINDOW_MAX}",
        )
    server_now = datetime.now(tz=UTC)
    data = await fetch_dashboard_requests(
        session=session,
        context=context,
        server_now=server_now,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        window_minutes=window_minutes,
        method=method,
        status_class=status_class,
        focus=focus,
        path_contains=path_contains,
        environments=environments,
        services=services,
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
        limit=export_limit,
        offset=export_offset,
        event_sql_filter=event_sql_filter,
        correlation_request_id=correlation_request_id,
    )
    safe_project = str(context.project_id).replace("/", "_")[:40]
    if export_format == "json":
        body = {
            "meta": {
                "project_id": str(context.project_id),
                "server_now": data.server_now.isoformat(),
                "from_timestamp": data.from_timestamp.isoformat(),
                "to_timestamp": data.to_timestamp.isoformat(),
                "total_in_scope": data.total,
                "export_limit": export_limit,
                "export_offset": export_offset,
                "returned_rows": len(data.items),
            },
            "items": [item.model_dump(mode="json") for item in data.items],
        }
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        filename = f"lumonox-requests-{safe_project}.json"
        return Response(
            content=raw,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_FIELDS)
    for item in data.items:
        row_dict = item.model_dump(mode="python")
        log_msg = row_dict.get("log_message")
        if isinstance(log_msg, str) and len(log_msg) > _EXPORT_LOG_MESSAGE_CSV_MAX:
            row_dict["log_message"] = log_msg[:_EXPORT_LOG_MESSAGE_CSV_MAX] + "…"
        writer.writerow([_csv_cell(row_dict.get(name)) for name in _CSV_FIELDS])
    filename = f"lumonox-requests-{safe_project}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
