from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.dashboard.duckdb_queries import (
    build_filters,
    diagnosis_timeline,
    error_group_events,
    failures_by_route,
)
from lumonox_backend.dashboard.error_grouping import (
    derived_error_group_key,
    error_like_events_predicate,
)
from lumonox_backend.dashboard.event_scope import http_scoped_event_types_clause
from lumonox_backend.dashboard.log_query import append_event_sql_filters
from lumonox_backend.dashboard.params import (
    EVENT_SQL_FILTER_QUERY,
    FROM_TIMESTAMP_QUERY,
    LIMIT_QUERY,
    OFFSET_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
)
from lumonox_backend.dashboard.time_window import (
    as_utc_datetime,
    iter_minute_buckets,
    minute_bucket,
    resolve_time_window,
)
from lumonox_backend.database import get_db_session
from lumonox_backend.ingestion.exclude_lumonox import (
    append_exclude_lumonox_event_filters,
    resolve_exclude_lumonox_traffic,
)
from lumonox_backend.models import Event
from lumonox_backend.schemas import (
    DashboardDiagnosisErrorGroupEventItem,
    DashboardDiagnosisErrorGroupEventsResponse,
    DashboardDiagnosisFailureRouteItem,
    DashboardDiagnosisFailureRoutesResponse,
    DashboardDiagnosisTimelineBucket,
    DashboardDiagnosisTimelineResponse,
)
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_plane_read_path import resolve_dashboard_read_store
from lumonox_backend.services.event_store import event_store_enabled

router = APIRouter()


def _fill_timeline_gaps(
    *,
    sparse_timeline: list[DashboardDiagnosisTimelineBucket],
    from_timestamp: datetime,
    to_timestamp: datetime,
) -> list[DashboardDiagnosisTimelineBucket]:
    by_minute = {bucket.minute: bucket for bucket in sparse_timeline}
    return [
        by_minute.get(
            minute,
            DashboardDiagnosisTimelineBucket(minute=minute, request_count=0, error_count=0),
        )
        for minute in iter_minute_buckets(from_timestamp, to_timestamp)
    ]


@router.get("/diagnosis/timeline", response_model=DashboardDiagnosisTimelineResponse)
async def get_dashboard_diagnosis_timeline(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
) -> DashboardDiagnosisTimelineResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        http_scoped_event_types_clause(),
    ]
    append_exclude_lumonox_event_filters(filters, exclude_lumonox_traffic=exclude_lumonox_traffic)
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
            exclude_lumonox_traffic=exclude_lumonox_traffic,
            event_sql_filter=event_sql_filter,
            http_events_only=True,
        )
        timeline = await run_duckdb_read_sync(
            diagnosis_timeline,
            duckdb_filters,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            store=read_store,
            duckdb_read_operation="diagnosis_timeline",
        )
        return DashboardDiagnosisTimelineResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            buckets=timeline,
        )
    rows = await session.execute(select(Event.timestamp, Event.status_code).where(*filters))
    buckets: dict[datetime, dict[str, int]] = {}
    for timestamp, status_code in rows:
        minute = minute_bucket(timestamp)
        bucket = buckets.setdefault(minute, {"requests": 0, "errors": 0})
        bucket["requests"] += 1
        if int(status_code) >= 500:
            bucket["errors"] += 1
    sparse_timeline = [
        DashboardDiagnosisTimelineBucket(
            minute=minute,
            request_count=data["requests"],
            error_count=data["errors"],
        )
        for minute, data in sorted(buckets.items(), key=lambda item: item[0])
    ]
    timeline = _fill_timeline_gaps(
        sparse_timeline=sparse_timeline,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
    )
    return DashboardDiagnosisTimelineResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        buckets=timeline,
    )


@router.get("/diagnosis/failures-by-route", response_model=DashboardDiagnosisFailureRoutesResponse)
async def get_dashboard_diagnosis_failures_by_route(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
) -> DashboardDiagnosisFailureRoutesResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        http_scoped_event_types_clause(),
    ]
    append_exclude_lumonox_event_filters(filters, exclude_lumonox_traffic=exclude_lumonox_traffic)
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
            exclude_lumonox_traffic=exclude_lumonox_traffic,
            event_sql_filter=event_sql_filter,
            http_events_only=True,
        )
        items = await run_duckdb_read_sync(
            failures_by_route,
            duckdb_filters,
            store=read_store,
            duckdb_read_operation="diagnosis_failures_by_route",
        )
        return DashboardDiagnosisFailureRoutesResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            items=items,
        )
    route_key = func.coalesce(Event.path, literal("unknown"))
    rows = await session.execute(
        select(
            route_key.label("path"),
            func.count(Event.id),
            func.sum(case((Event.status_code >= 500, 1), else_=0)),
            func.sum(Event.latency_ms),
        )
        .where(*filters)
        .group_by(route_key)
        .having(func.sum(case((Event.status_code >= 500, 1), else_=0)) > 0)
    )
    items = [
        DashboardDiagnosisFailureRouteItem(
            path=str(path or "unknown"),
            failure_count=int(failures or 0),
            error_rate=(int(failures or 0) / int(req_count or 0)) if int(req_count or 0) else 0.0,
            avg_latency_ms=(
                (float(lat_sum or 0.0) / int(req_count or 0)) if int(req_count or 0) else 0.0
            ),
        )
        for path, req_count, failures, lat_sum in rows
    ]
    items.sort(key=lambda item: item.failure_count, reverse=True)
    return DashboardDiagnosisFailureRoutesResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        items=items[:20],
    )


@router.get(
    "/diagnosis/error-group-events", response_model=DashboardDiagnosisErrorGroupEventsResponse
)
async def get_dashboard_diagnosis_error_group_events(
    group_key: str,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    limit: int = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
) -> DashboardDiagnosisErrorGroupEventsResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    _ = server_now
    exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        error_like_events_predicate(resolved_from, resolved_to),
    ]
    append_exclude_lumonox_event_filters(filters, exclude_lumonox_traffic=exclude_lumonox_traffic)
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
            exclude_lumonox_traffic=exclude_lumonox_traffic,
            event_sql_filter=event_sql_filter,
            http_events_only=True,
        )
        total, items = await run_duckdb_read_sync(
            error_group_events,
            duckdb_filters,
            group_key=group_key,
            limit=limit,
            offset=offset,
            store=read_store,
            duckdb_read_operation="diagnosis_error_group_events",
        )
        return DashboardDiagnosisErrorGroupEventsResponse(total=total, items=items)
    rows = await session.execute(
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
            Event.payload,
        )
        .where(*filters)
        .order_by(Event.timestamp.desc(), Event.id.desc())
    )
    matched: list[DashboardDiagnosisErrorGroupEventItem] = []
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
        payload,
    ) in rows:
        payload_dict = payload if isinstance(payload, dict) else {}
        ev_path = path if isinstance(path, str) else ""
        derived_key = derived_error_group_key(payload_dict, ev_path)
        if derived_key != group_key:
            continue
        matched.append(
            DashboardDiagnosisErrorGroupEventItem(
                id=int(event_id),
                timestamp=as_utc_datetime(timestamp),
                method=method,
                path=path,
                status_code=int(status_code),
                latency_ms=float(latency_ms),
                service_name=service_name,
                environment=environment,
                request_id=request_id,
                stack_trace=payload_dict.get("stack_trace")
                if isinstance(payload_dict.get("stack_trace"), str)
                else None,
                message=payload_dict.get("exception_message")
                if isinstance(payload_dict.get("exception_message"), str)
                else None,
                exception_type=payload_dict.get("exception_type")
                if isinstance(payload_dict.get("exception_type"), str)
                else None,
            )
        )
    paged = matched[offset : offset + limit]
    return DashboardDiagnosisErrorGroupEventsResponse(total=len(matched), items=paged)
