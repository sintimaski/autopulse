from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_dashboard_project
from autopulse_backend.dashboard.log_query import append_event_sql_filters, percentile
from autopulse_backend.dashboard.params import (
    EVENT_SQL_FILTER_QUERY,
    FROM_TIMESTAMP_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
)
from autopulse_backend.dashboard.time_window import (
    as_utc_datetime,
    iter_minute_buckets,
    minute_bucket,
    resolve_time_window,
)
from autopulse_backend.db import get_db_session
from autopulse_backend.exclude_autopulse import (
    append_exclude_autopulse_event_filters,
    resolve_exclude_autopulse_traffic,
)
from autopulse_backend.models import Event
from autopulse_backend.schemas import (
    DashboardBreakdownItem,
    DashboardOverviewBucket,
    DashboardOverviewExtendedResponse,
    DashboardOverviewResponse,
)

router = APIRouter()


def _empty_overview_bucket(minute: datetime) -> DashboardOverviewBucket:
    return DashboardOverviewBucket(
        minute=minute,
        request_count=0,
        error_count=0,
        avg_latency_ms=0.0,
        count_2xx=0,
        count_3xx=0,
        count_4xx=0,
        count_5xx=0,
    )


def _fill_overview_series_gaps(
    *,
    sparse_series: list[DashboardOverviewBucket],
    from_timestamp: datetime,
    to_timestamp: datetime,
) -> list[DashboardOverviewBucket]:
    by_minute = {bucket.minute: bucket for bucket in sparse_series}
    return [
        by_minute.get(minute, _empty_overview_bucket(minute))
        for minute in iter_minute_buckets(from_timestamp, to_timestamp)
    ]


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
) -> DashboardOverviewResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    exclude_autopulse_traffic = await resolve_exclude_autopulse_traffic(session, context.project_id)
    error_condition = (Event.type == "error") | (Event.status_code >= 500)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
    ]
    append_exclude_autopulse_event_filters(
        filters, exclude_autopulse_traffic=exclude_autopulse_traffic
    )
    append_event_sql_filters(filters, event_sql_filter)

    totals_query = select(
        func.count(Event.id),
        func.sum(case((error_condition, 1), else_=0)),
        func.avg(Event.latency_ms),
    ).where(*filters)
    totals_result = await session.execute(totals_query)
    request_count, error_count, avg_latency = totals_result.one()

    request_total = int(request_count or 0)
    error_total = int(error_count or 0)
    avg_latency_ms = float(avg_latency or 0.0)
    window_minutes_val = max((resolved_to - resolved_from).total_seconds() / 60.0, 1.0)
    error_rate = (error_total / request_total) if request_total else 0.0
    requests_per_minute = request_total / window_minutes_val

    dialect_name = session.bind.dialect.name if session.bind is not None else ""
    if dialect_name == "sqlite":
        series_rows = await session.execute(
            select(Event.timestamp, Event.type, Event.status_code, Event.latency_ms).where(*filters)
        )
        buckets: dict[datetime, dict[str, float | int]] = {}
        for timestamp, event_type, status_code, latency_ms in series_rows:
            bucket = minute_bucket(timestamp)
            current = buckets.setdefault(
                bucket,
                {
                    "request_count": 0,
                    "error_count": 0,
                    "latency_sum": 0.0,
                    "count_2xx": 0,
                    "count_3xx": 0,
                    "count_4xx": 0,
                    "count_5xx": 0,
                },
            )
            current["request_count"] += 1
            if event_type == "error" or status_code >= 500:
                current["error_count"] += 1
            status_class = int(status_code or 0) // 100
            if status_class == 2:
                current["count_2xx"] += 1
            elif status_class == 3:
                current["count_3xx"] += 1
            elif status_class == 4:
                current["count_4xx"] += 1
            elif status_class == 5:
                current["count_5xx"] += 1
            current["latency_sum"] += float(latency_ms)
        sparse_series = [
            DashboardOverviewBucket(
                minute=bucket,
                request_count=int(data["request_count"]),
                error_count=int(data["error_count"]),
                avg_latency_ms=(
                    float(data["latency_sum"]) / int(data["request_count"])
                    if int(data["request_count"]) > 0
                    else 0.0
                ),
                count_2xx=int(data["count_2xx"]),
                count_3xx=int(data["count_3xx"]),
                count_4xx=int(data["count_4xx"]),
                count_5xx=int(data["count_5xx"]),
            )
            for bucket, data in sorted(buckets.items(), key=lambda item: item[0])
        ]
    else:
        series_query = (
            select(
                func.date_trunc("minute", Event.timestamp).label("minute_bucket"),
                func.count(Event.id),
                func.sum(case((error_condition, 1), else_=0)),
                func.avg(Event.latency_ms),
                func.sum(case((Event.status_code.between(200, 299), 1), else_=0)),
                func.sum(case((Event.status_code.between(300, 399), 1), else_=0)),
                func.sum(case((Event.status_code.between(400, 499), 1), else_=0)),
                func.sum(case((Event.status_code.between(500, 599), 1), else_=0)),
            )
            .where(
                *filters,
            )
            .group_by("minute_bucket")
            .order_by("minute_bucket")
        )
        series_result = await session.execute(series_query)
        sparse_series = [
            DashboardOverviewBucket(
                minute=as_utc_datetime(minute_bucket),
                request_count=int(bucket_request_count or 0),
                error_count=int(bucket_error_count or 0),
                avg_latency_ms=float(bucket_avg_latency or 0.0),
                count_2xx=int(bucket_2xx_count or 0),
                count_3xx=int(bucket_3xx_count or 0),
                count_4xx=int(bucket_4xx_count or 0),
                count_5xx=int(bucket_5xx_count or 0),
            )
            for (
                minute_bucket,
                bucket_request_count,
                bucket_error_count,
                bucket_avg_latency,
                bucket_2xx_count,
                bucket_3xx_count,
                bucket_4xx_count,
                bucket_5xx_count,
            ) in series_result
        ]
    series = _fill_overview_series_gaps(
        sparse_series=sparse_series,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
    )

    return DashboardOverviewResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        request_count=request_total,
        error_count=error_total,
        error_rate=error_rate,
        avg_latency_ms=avg_latency_ms,
        requests_per_minute=requests_per_minute,
        series=series,
    )


@router.get("/overview/extended", response_model=DashboardOverviewExtendedResponse)
async def get_dashboard_overview_extended(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = TO_TIMESTAMP_QUERY,
    window_minutes: int = WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = EVENT_SQL_FILTER_QUERY,
) -> DashboardOverviewExtendedResponse:
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
    append_event_sql_filters(filters, event_sql_filter)
    rows = await session.execute(
        select(
            Event.path,
            Event.service_name,
            Event.status_code,
            Event.latency_ms,
            Event.timestamp,
        ).where(*filters)
    )
    items = list(rows)
    latencies = [float(latency) for _, _, _, latency, _ in items]

    service_stats: dict[str, dict[str, float | int]] = {}
    route_stats: dict[str, dict[str, float | int]] = {}
    error_burst_count = 0
    error_window_start = resolved_to - timedelta(minutes=5)
    for path, service_name, status_code, latency_ms, timestamp in items:
        is_error = int(status_code) >= 500
        key_service = service_name or "unknown"
        key_route = path or "unknown"
        for stats, key in ((service_stats, key_service), (route_stats, key_route)):
            current = stats.setdefault(
                key,
                {"requests": 0, "errors": 0, "latency_sum": 0.0},
            )
            current["requests"] += 1
            current["latency_sum"] += float(latency_ms)
            if is_error:
                current["errors"] += 1
        if is_error and as_utc_datetime(timestamp) >= error_window_start:
            error_burst_count += 1

    def to_breakdown(source: dict[str, dict[str, float | int]]) -> list[DashboardBreakdownItem]:
        rows_result: list[DashboardBreakdownItem] = []
        for key, data in source.items():
            req = int(data["requests"])
            err = int(data["errors"])
            rows_result.append(
                DashboardBreakdownItem(
                    key=key,
                    request_count=req,
                    error_count=err,
                    error_rate=(err / req) if req else 0.0,
                    avg_latency_ms=(float(data["latency_sum"]) / req) if req else 0.0,
                )
            )
        rows_result.sort(key=lambda row: (row.error_count, row.request_count), reverse=True)
        return rows_result[:8]

    return DashboardOverviewExtendedResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        p50_latency_ms=percentile(latencies, 0.50),
        p95_latency_ms=percentile(latencies, 0.95),
        p99_latency_ms=percentile(latencies, 0.99),
        error_burst_count=error_burst_count,
        active_incident_count=1 if error_burst_count > 0 else 0,
        service_breakdown=to_breakdown(service_stats),
        route_breakdown=to_breakdown(route_stats),
    )
