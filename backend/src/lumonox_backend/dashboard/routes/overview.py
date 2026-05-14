from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.dashboard.duckdb_queries import (
    build_filters,
    overview_extended,
    overview_release_markers,
    overview_series,
)
from lumonox_backend.dashboard.event_scope import http_scoped_event_types_clause
from lumonox_backend.dashboard.log_query import append_event_sql_filters, percentile
from lumonox_backend.dashboard.params import (
    EVENT_SQL_FILTER_QUERY,
    FROM_TIMESTAMP_QUERY,
    TO_TIMESTAMP_QUERY,
    WINDOW_MINUTES_QUERY,
)
from lumonox_backend.dashboard.release_markers import fetch_release_markers_for_event_filters
from lumonox_backend.dashboard.time_window import (
    as_utc_datetime,
    hour_bucket,
    iter_minute_buckets,
    minute_bucket,
    overview_use_hourly_buckets,
    resolve_time_window,
)
from lumonox_backend.database import get_db_session
from lumonox_backend.ingestion.exclude_lumonox import (
    append_exclude_lumonox_event_filters,
    resolve_exclude_lumonox_traffic,
)
from lumonox_backend.models import AlertDispatch, Event, MetricBucket
from lumonox_backend.repositories.metric_bucket_overview import (
    MetricBucketDisplayRollup,
    fetch_metric_bucket_rollups_for_overview,
)
from lumonox_backend.schemas import (
    DashboardAlertTimelineItem,
    DashboardBreakdownItem,
    DashboardErrorTypeBreakdownItem,
    DashboardOverviewBucket,
    DashboardOverviewExtendedResponse,
    DashboardOverviewResponse,
)
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_plane_read_path import resolve_dashboard_read_store
from lumonox_backend.services.event_store import event_store_enabled

router = APIRouter()
APDEX_SATISFIED_THRESHOLD_MS = 300.0
APDEX_TOLERATED_THRESHOLD_MS = 1200.0


def _compute_apdex(latencies: list[float]) -> float:
    total = len(latencies)
    if total == 0:
        return 1.0
    satisfied = sum(1 for latency in latencies if latency <= APDEX_SATISFIED_THRESHOLD_MS)
    tolerated = sum(
        1
        for latency in latencies
        if APDEX_SATISFIED_THRESHOLD_MS < latency <= APDEX_TOLERATED_THRESHOLD_MS
    )
    return (satisfied + (tolerated / 2.0)) / float(total)


def _classify_error_type(
    *, event_type: str, status_code: int, payload: dict[str, object]
) -> str | None:
    if event_type != "error" and status_code < 500:
        return None
    exception_type = str(payload.get("exception_type") or "")
    exception_message = str(payload.get("exception_message") or "")
    raw = f"{exception_type} {exception_message}".lower()
    if "timeout" in raw or "timed out" in raw:
        return "timeout"
    if any(token in raw for token in ("sql", "database", "db", "postgres", "mysql", "sqlite")):
        return "database"
    if any(token in raw for token in ("validation", "pydantic", "invalid")):
        return "validation"
    if any(
        token in raw
        for token in ("network", "connection", "dns", "socket", "refused", "unreachable")
    ):
        return "network"
    if any(token in raw for token in ("auth", "unauthorized", "forbidden", "token")):
        return "auth"
    return "server"


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


def _merge_duckdb_overview_series_with_sql_metric_buckets(
    *,
    series: list[DashboardOverviewBucket],
    rollups: dict[datetime, MetricBucketDisplayRollup],
    use_hourly: bool,
) -> list[DashboardOverviewBucket]:
    """When raw DuckDB rows were trimmed but SQLite minute aggregates remain, fill empty buckets.

    If a display bucket already has DuckDB traffic (``request_count > 0``), DuckDB wins to avoid
    double-counting when both stores cover the same ingest window.
    """
    bucket_fn = hour_bucket if use_hourly else minute_bucket
    merged: list[DashboardOverviewBucket] = []
    for b in series:
        key = bucket_fn(as_utc_datetime(b.minute))
        if b.request_count > 0:
            merged.append(b)
            continue
        raw = rollups.get(key)
        if not isinstance(raw, MetricBucketDisplayRollup) or raw.request_count <= 0:
            merged.append(b)
            continue
        avg = float(raw.latency_total_ms) / float(raw.request_count) if raw.request_count else 0.0
        merged.append(
            DashboardOverviewBucket(
                minute=b.minute,
                request_count=raw.request_count,
                error_count=raw.error_count,
                avg_latency_ms=avg,
                count_2xx=raw.count_2xx,
                count_3xx=raw.count_3xx,
                count_4xx=raw.count_4xx,
                count_5xx=raw.count_5xx,
            )
        )
    return merged


def _overview_totals_from_series(series: list[DashboardOverviewBucket]) -> tuple[int, int, float]:
    request_total = 0
    error_total = 0
    latency_weighted = 0.0
    for b in series:
        rc = int(b.request_count)
        request_total += rc
        error_total += int(b.error_count)
        latency_weighted += float(b.avg_latency_ms) * rc
    avg_latency_ms = latency_weighted / request_total if request_total else 0.0
    return request_total, error_total, avg_latency_ms


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
    exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, context.project_id)
    error_condition = (Event.type == "error") | (Event.status_code >= 500)
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
        request_total, error_total, avg_latency_ms, series = await run_duckdb_read_sync(
            overview_series,
            duckdb_filters,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            store=read_store,
            duckdb_read_operation="overview",
        )
        if not event_sql_filter:
            use_hourly = overview_use_hourly_buckets(resolved_from, resolved_to)
            rollups = await fetch_metric_bucket_rollups_for_overview(
                session,
                project_id=context.project_id,
                from_timestamp=resolved_from,
                to_timestamp=resolved_to,
                use_hourly=use_hourly,
            )
            series = _merge_duckdb_overview_series_with_sql_metric_buckets(
                series=series,
                rollups=rollups,
                use_hourly=use_hourly,
            )
            request_total, error_total, avg_latency_ms = _overview_totals_from_series(series)
        window_minutes_val = max((resolved_to - resolved_from).total_seconds() / 60.0, 1.0)
        release_markers = await run_duckdb_read_sync(
            overview_release_markers,
            duckdb_filters,
            store=read_store,
            duckdb_read_operation="overview_release_markers",
        )
        return DashboardOverviewResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            request_count=request_total,
            error_count=error_total,
            error_rate=(error_total / request_total) if request_total else 0.0,
            avg_latency_ms=avg_latency_ms,
            requests_per_minute=request_total / window_minutes_val,
            series=series,
            release_markers=release_markers,
        )

    if not exclude_lumonox_traffic and not event_sql_filter:
        bucket_rows = await session.execute(
            select(
                MetricBucket.minute_start,
                func.sum(MetricBucket.request_count),
                func.sum(MetricBucket.error_count),
                func.sum(MetricBucket.latency_total_ms),
                func.sum(MetricBucket.count_2xx),
                func.sum(MetricBucket.count_3xx),
                func.sum(MetricBucket.count_4xx),
                func.sum(MetricBucket.count_5xx),
            )
            .where(
                MetricBucket.project_id == context.project_id,
                MetricBucket.minute_start >= resolved_from,
                MetricBucket.minute_start <= resolved_to,
            )
            .group_by(MetricBucket.minute_start)
            .order_by(MetricBucket.minute_start.asc())
        )
        sparse_series: list[DashboardOverviewBucket] = []
        request_total = 0
        error_total = 0
        latency_total = 0.0
        for (
            minute_start,
            bucket_request_count,
            bucket_error_count,
            bucket_latency_total,
            bucket_2xx_count,
            bucket_3xx_count,
            bucket_4xx_count,
            bucket_5xx_count,
        ) in bucket_rows:
            request_count = int(bucket_request_count or 0)
            request_total += request_count
            error_total += int(bucket_error_count or 0)
            latency_total += float(bucket_latency_total or 0.0)
            sparse_series.append(
                DashboardOverviewBucket(
                    minute=as_utc_datetime(minute_start),
                    request_count=request_count,
                    error_count=int(bucket_error_count or 0),
                    avg_latency_ms=(
                        float(bucket_latency_total or 0.0) / request_count if request_count else 0.0
                    ),
                    count_2xx=int(bucket_2xx_count or 0),
                    count_3xx=int(bucket_3xx_count or 0),
                    count_4xx=int(bucket_4xx_count or 0),
                    count_5xx=int(bucket_5xx_count or 0),
                )
            )
        window_minutes_val = max((resolved_to - resolved_from).total_seconds() / 60.0, 1.0)
        error_rate = (error_total / request_total) if request_total else 0.0
        requests_per_minute = request_total / window_minutes_val
        avg_latency_ms = latency_total / request_total if request_total else 0.0
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
            release_markers=[],
        )

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

    dialect_name = session.bind.dialect.name if session.bind is not None else ""
    release_markers = await fetch_release_markers_for_event_filters(
        session, dialect_name=dialect_name, filters=filters
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
        release_markers=release_markers,
    )


async def _load_alerts_timeline(
    session: AsyncSession,
    *,
    project_id: UUID,
    resolved_from: datetime,
    resolved_to: datetime,
) -> list[DashboardAlertTimelineItem]:
    """Alert dispatches in the window. Lives in the relational DB regardless of event store,
    so both the DuckDB and SQL overview-extended paths share this."""
    alert_rows = await session.execute(
        select(AlertDispatch.triggered_at, AlertDispatch.alert_type, AlertDispatch.status)
        .where(
            AlertDispatch.project_id == project_id,
            AlertDispatch.triggered_at >= resolved_from,
            AlertDispatch.triggered_at <= resolved_to,
        )
        .order_by(AlertDispatch.triggered_at.asc(), AlertDispatch.id.asc())
        .limit(200)
    )
    return [
        DashboardAlertTimelineItem(
            triggered_at=as_utc_datetime(triggered_at),
            alert_type=str(alert_type),
            status=str(status),
        )
        for triggered_at, alert_type, status in alert_rows
    ]


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
        data = await run_duckdb_read_sync(
            overview_extended,
            duckdb_filters,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            store=read_store,
            duckdb_read_operation="overview_extended",
        )
        alerts_timeline = await _load_alerts_timeline(
            session,
            project_id=context.project_id,
            resolved_from=resolved_from,
            resolved_to=resolved_to,
        )
        return DashboardOverviewExtendedResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            p50_latency_ms=data["p50_latency_ms"],
            p95_latency_ms=data["p95_latency_ms"],
            p99_latency_ms=data["p99_latency_ms"],
            apdex_score=data["apdex_score"],
            active_sessions_estimate=data["active_sessions_estimate"],
            error_burst_count=data["error_burst_count"],
            active_incident_count=data["active_incident_count"],
            error_type_breakdown=[
                DashboardErrorTypeBreakdownItem(error_type=item["error_type"], count=item["count"])
                for item in data["error_type_breakdown"]
            ],
            alerts_timeline=alerts_timeline,
            service_breakdown=[
                DashboardBreakdownItem(**item) for item in data["service_breakdown"]
            ],
            route_breakdown=[DashboardBreakdownItem(**item) for item in data["route_breakdown"]],
        )

    # Avoid loading full JSON payloads for every row in the window (can be GB+ of I/O); use
    # SQL aggregates and small targeted reads for error classification and session hints.
    latencies = [
        float(v) for v in (await session.scalars(select(Event.latency_ms).where(*filters))).all()
    ]

    error_window_start = resolved_to - timedelta(minutes=5)
    error_burst_result = await session.execute(
        select(func.count(Event.id)).where(
            *filters,
            Event.status_code >= 500,
            Event.timestamp >= error_window_start,
        )
    )
    error_burst_count = int(error_burst_result.scalar_one() or 0)

    service_key = func.coalesce(Event.service_name, literal("unknown"))
    service_agg = await session.execute(
        select(
            service_key.label("key"),
            func.count(Event.id),
            func.sum(case((Event.status_code >= 500, 1), else_=0)),
            func.sum(Event.latency_ms),
        )
        .where(*filters)
        .group_by(service_key)
    )
    service_stats = {
        str(key or "unknown"): {
            "requests": int(reqs or 0),
            "errors": int(errs or 0),
            "latency_sum": float(lat_sum or 0.0),
        }
        for key, reqs, errs, lat_sum in service_agg
    }

    route_key = func.coalesce(Event.path, literal("unknown"))
    route_agg = await session.execute(
        select(
            route_key.label("key"),
            func.count(Event.id),
            func.sum(case((Event.status_code >= 500, 1), else_=0)),
            func.sum(Event.latency_ms),
        )
        .where(*filters)
        .group_by(route_key)
    )
    route_stats = {
        str(key or "unknown"): {
            "requests": int(reqs or 0),
            "errors": int(errs or 0),
            "latency_sum": float(lat_sum or 0.0),
        }
        for key, reqs, errs, lat_sum in route_agg
    }

    error_type_counts: Counter[str] = Counter()
    error_like = or_(Event.type == "error", Event.status_code >= 500)
    error_rows = await session.execute(
        select(Event.type, Event.status_code, Event.payload).where(*filters, error_like)
    )
    for event_type, status_code, payload in error_rows:
        payload_dict = payload if isinstance(payload, dict) else {}
        classified = _classify_error_type(
            event_type=str(event_type or ""),
            status_code=int(status_code or 0),
            payload=payload_dict,
        )
        if classified is not None:
            error_type_counts[classified] += 1

    active_session_keys: set[str] = set()
    identity_rows = await session.execute(
        select(
            Event.request_id,
            Event.payload["session_id"].as_string(),
            Event.payload["sessionId"].as_string(),
            Event.payload["user_id"].as_string(),
            Event.payload["userId"].as_string(),
            Event.payload["distinct_id"].as_string(),
        ).where(*filters)
    )
    for request_id, sid, sid_alt, uid, uid_alt, did in identity_rows:
        chosen: str | None = None
        for raw in (sid, sid_alt, uid, uid_alt, did):
            if isinstance(raw, str) and raw.strip():
                chosen = raw.strip()
                break
            if isinstance(raw, int | float) and not isinstance(raw, bool):
                chosen = str(int(raw))
                break
        if chosen:
            active_session_keys.add(chosen)
        elif isinstance(request_id, str) and request_id.strip():
            active_session_keys.add(request_id.strip())

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

    alerts_timeline = await _load_alerts_timeline(
        session,
        project_id=context.project_id,
        resolved_from=resolved_from,
        resolved_to=resolved_to,
    )

    return DashboardOverviewExtendedResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        p50_latency_ms=percentile(latencies, 0.50),
        p95_latency_ms=percentile(latencies, 0.95),
        p99_latency_ms=percentile(latencies, 0.99),
        apdex_score=_compute_apdex(latencies),
        active_sessions_estimate=len(active_session_keys),
        error_burst_count=error_burst_count,
        active_incident_count=1 if error_burst_count > 0 else 0,
        error_type_breakdown=[
            DashboardErrorTypeBreakdownItem(error_type=error_type, count=count)
            for error_type, count in error_type_counts.most_common(8)
        ],
        alerts_timeline=alerts_timeline,
        service_breakdown=to_breakdown(service_stats),
        route_breakdown=to_breakdown(route_stats),
    )
