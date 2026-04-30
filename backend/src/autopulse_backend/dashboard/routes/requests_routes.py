from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_dashboard_project
from autopulse_backend.dashboard.duckdb_queries import build_filters, request_items
from autopulse_backend.dashboard.log_query import append_event_sql_filters
from autopulse_backend.dashboard.messages import dashboard_request_log_message
from autopulse_backend.dashboard.params import (
    ENVIRONMENTS_QUERY,
    EVENT_SQL_FILTER_QUERY,
    FROM_TIMESTAMP_QUERY,
    LATENCY_MAX_MS_QUERY,
    LATENCY_MIN_MS_QUERY,
    LIMIT_QUERY,
    METHOD_QUERY,
    OFFSET_QUERY,
    PATH_QUERY,
    SERVICES_QUERY,
    STATUS_CLASS_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
)
from autopulse_backend.dashboard.parsing import split_csv_values
from autopulse_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from autopulse_backend.database import get_db_session
from autopulse_backend.ingestion.exclude_autopulse import (
    append_exclude_autopulse_event_filters,
    resolve_exclude_autopulse_traffic,
)
from autopulse_backend.models import Event
from autopulse_backend.schemas import DashboardRequestItem, DashboardRequestsResponse
from autopulse_backend.services.event_store import event_store_enabled

router = APIRouter()


@router.get("/requests", response_model=DashboardRequestsResponse)
async def get_dashboard_requests(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    method: str | None = METHOD_QUERY,
    status_class: int | None = STATUS_CLASS_QUERY,
    path_contains: str | None = PATH_QUERY,
    environments: str | None = ENVIRONMENTS_QUERY,
    services: str | None = SERVICES_QUERY,
    min_latency_ms: float | None = LATENCY_MIN_MS_QUERY,
    max_latency_ms: float | None = LATENCY_MAX_MS_QUERY,
    limit: int = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
) -> DashboardRequestsResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    exclude_autopulse_traffic = await resolve_exclude_autopulse_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
    ]
    append_exclude_autopulse_event_filters(
        filters, exclude_autopulse_traffic=exclude_autopulse_traffic
    )
    if method:
        filters.append(Event.method == method.upper())
    if status_class is not None:
        lower = status_class * 100
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
        duckdb_filters = build_filters(
            project_id=context.project_id,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            method=method,
            status_class=status_class,
            path_contains=path_contains,
            environments=environments,
            services=services,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            exclude_autopulse_traffic=exclude_autopulse_traffic,
            event_sql_filter=event_sql_filter,
        )
        total, items = await asyncio.to_thread(
            request_items, duckdb_filters, limit=limit, offset=offset
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
            Event.timestamp,
            Event.method,
            Event.path,
            Event.status_code,
            Event.latency_ms,
            Event.service_name,
            Event.environment,
            Event.request_id,
            Event.type,
            Event.payload,
        )
        .where(*filters)
        .order_by(Event.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    requests_result = await session.execute(requests_query)
    items = [
        DashboardRequestItem(
            timestamp=as_utc_datetime(timestamp),
            method=event_method,
            path=path,
            status_code=status_code,
            latency_ms=latency_ms,
            service_name=service_name,
            environment=environment,
            request_id=request_id,
            log_message=dashboard_request_log_message(event_type, payload),
        )
        for (
            timestamp,
            event_method,
            path,
            status_code,
            latency_ms,
            service_name,
            environment,
            request_id,
            event_type,
            payload,
        ) in requests_result
    ]
    return DashboardRequestsResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )
