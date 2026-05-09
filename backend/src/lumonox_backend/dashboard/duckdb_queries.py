from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from lumonox_backend.dashboard.duckdb_query_utils import (
    dashboard_list_payload_cell,
    first_non_empty_str,
    truncate_diagnosis_text,
)
from lumonox_backend.dashboard.error_grouping import (
    derived_error_group_key,
    error_group_labels,
)
from lumonox_backend.dashboard.messages import dashboard_request_log_message
from lumonox_backend.dashboard.parsing import split_csv_values
from lumonox_backend.dashboard.payload_limits import (
    MAX_DIAGNOSIS_EVENT_MESSAGE_CHARS,
    MAX_DIAGNOSIS_EVENT_STACK_CHARS,
)
from lumonox_backend.dashboard.time_window import (
    as_utc_datetime,
    iter_minute_buckets,
    minute_bucket,
)
from lumonox_backend.schemas import (
    DashboardDiagnosisErrorGroupEventItem,
    DashboardDiagnosisFailureRouteItem,
    DashboardDiagnosisTimelineBucket,
    DashboardErrorGroupItem,
    DashboardOverviewBucket,
    DashboardRequestItem,
)
from lumonox_backend.services.event_store import (
    DuckDbEventStore,
    EventStoreFilters,
    get_duckdb_event_store,
)

EVENT_SELECT_COLUMNS = (
    "id, timestamp, method, path, status_code, latency_ms, "
    "service_name, environment, request_id, type, payload"
)
MAX_ERROR_GROUP_SCAN_ROWS = 20_000


def build_filters(
    *,
    project_id: UUID,
    from_timestamp: datetime,
    to_timestamp: datetime,
    exclude_lumonox_traffic: bool,
    method: str | None = None,
    status_class: int | None = None,
    path_contains: str | None = None,
    environments: str | None = None,
    services: str | None = None,
    min_latency_ms: float | None = None,
    max_latency_ms: float | None = None,
    event_sql_filter: str | None = None,
    http_events_only: bool = True,
    require_event_types: tuple[str, ...] | None = None,
    include_received_at_in_time_window: bool = False,
    skip_timestamp_filter: bool = False,
) -> EventStoreFilters:
    return EventStoreFilters(
        project_id=project_id,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        exclude_lumonox_traffic=exclude_lumonox_traffic,
        method=method,
        status_class=status_class,
        path_contains=path_contains,
        environments=tuple(split_csv_values(environments)),
        services=tuple(split_csv_values(services)),
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
        event_sql_filter=event_sql_filter,
        http_events_only=http_events_only,
        require_event_types=require_event_types,
        include_received_at_in_time_window=include_received_at_in_time_window,
        skip_timestamp_filter=skip_timestamp_filter,
    )


def request_items(
    filters: EventStoreFilters, *, limit: int, offset: int, store: DuckDbEventStore | None = None
) -> tuple[int, list[DashboardRequestItem]]:
    resolved_store = store if store is not None else get_duckdb_event_store()
    total, rows = resolved_store.fetch_events_with_total(
        filters, limit=limit, offset=offset, slim_payload=True
    )
    return total, [
        DashboardRequestItem(
            timestamp=as_utc_datetime(timestamp),
            method=method,
            path=path,
            status_code=int(status_code),
            latency_ms=float(latency_ms),
            service_name=service_name,
            environment=environment,
            request_id=request_id,
            log_message=dashboard_request_log_message(
                event_type, dashboard_list_payload_cell(payload)
            ),
            event_id=int(_event_id) if _event_id is not None else None,
            received_at=as_utc_datetime(received_at) if received_at is not None else None,
            sdk_version=str(sdk_version) if sdk_version is not None else None,
            event_kind=str(event_type) if event_type is not None else None,
            trace_id=first_non_empty_str(trace_id, trace_id_alt),
            span_id=first_non_empty_str(span_id, span_id_alt),
        )
        for (
            _event_id,
            timestamp,
            method,
            path,
            status_code,
            latency_ms,
            service_name,
            environment,
            request_id,
            event_type,
            payload,
            received_at,
            sdk_version,
            trace_id,
            trace_id_alt,
            span_id,
            span_id_alt,
        ) in rows
    ]


def overview_series(
    filters: EventStoreFilters,
    *,
    from_timestamp: datetime,
    to_timestamp: datetime,
    store: DuckDbEventStore | None = None,
) -> tuple[int, int, float, list[DashboardOverviewBucket]]:
    resolved_store = store if store is not None else get_duckdb_event_store()
    rows = resolved_store.query_events_sql(
        filters,
        select_sql="""
            date_trunc('minute', timestamp) AS minute,
            COUNT(*) AS request_count,
            SUM(CASE WHEN type = 'error' OR status_code >= 500 THEN 1 ELSE 0 END) AS error_count,
            AVG(latency_ms) AS avg_latency_ms,
            SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) AS count_2xx,
            SUM(CASE WHEN status_code >= 300 AND status_code < 400 THEN 1 ELSE 0 END) AS count_3xx,
            SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) AS count_4xx,
            SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS count_5xx
        """,
        suffix_sql="GROUP BY 1 ORDER BY 1 ASC",
    )
    buckets: dict[datetime, dict[str, float | int]] = {}
    request_count = 0
    error_count = 0
    latency_total = 0.0
    for (
        minute,
        minute_request_count,
        minute_error_count,
        minute_avg_latency_ms,
        count_2xx,
        count_3xx,
        count_4xx,
        count_5xx,
    ) in rows:
        minute_requests = int(minute_request_count or 0)
        minute_errors = int(minute_error_count or 0)
        request_count += minute_requests
        error_count += minute_errors
        latency_total += float(minute_avg_latency_ms or 0.0) * minute_requests
        bucket = buckets.setdefault(
            minute_bucket(minute),
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
        bucket["request_count"] += minute_requests
        bucket["latency_sum"] += float(minute_avg_latency_ms or 0.0) * minute_requests
        bucket["error_count"] += minute_errors
        bucket["count_2xx"] += int(count_2xx or 0)
        bucket["count_3xx"] += int(count_3xx or 0)
        bucket["count_4xx"] += int(count_4xx or 0)
        bucket["count_5xx"] += int(count_5xx or 0)
    sparse = {
        dt: DashboardOverviewBucket(
            minute=dt,
            request_count=int(data["request_count"]),
            error_count=int(data["error_count"]),
            avg_latency_ms=(float(data["latency_sum"]) / int(data["request_count"]))
            if int(data["request_count"])
            else 0.0,
            count_2xx=int(data["count_2xx"]),
            count_3xx=int(data["count_3xx"]),
            count_4xx=int(data["count_4xx"]),
            count_5xx=int(data["count_5xx"]),
        )
        for dt, data in buckets.items()
    }
    series = [
        sparse.get(
            minute,
            DashboardOverviewBucket(
                minute=minute,
                request_count=0,
                error_count=0,
                avg_latency_ms=0.0,
                count_2xx=0,
                count_3xx=0,
                count_4xx=0,
                count_5xx=0,
            ),
        )
        for minute in iter_minute_buckets(from_timestamp, to_timestamp)
    ]
    avg_latency = latency_total / request_count if request_count else 0.0
    return request_count, error_count, avg_latency, series


def diagnosis_timeline(
    filters: EventStoreFilters,
    *,
    from_timestamp: datetime,
    to_timestamp: datetime,
    store: DuckDbEventStore | None = None,
) -> list[DashboardDiagnosisTimelineBucket]:
    resolved_store = store if store is not None else get_duckdb_event_store()
    rows = resolved_store.query_events_sql(
        filters,
        select_sql=(
            "date_trunc('minute', timestamp) AS minute, "
            "COUNT(*) AS request_count, "
            "SUM(CASE WHEN type = 'error' OR status_code >= 500 THEN 1 ELSE 0 END) AS error_count"
        ),
        suffix_sql="GROUP BY 1 ORDER BY 1 ASC",
    )
    by_minute: dict[datetime, dict[str, int]] = {}
    for minute, request_count, error_count in rows:
        by_minute[minute_bucket(minute)] = {
            "request_count": int(request_count or 0),
            "error_count": int(error_count or 0),
        }
    mapped = {
        minute: DashboardDiagnosisTimelineBucket(
            minute=minute,
            request_count=data["request_count"],
            error_count=data["error_count"],
        )
        for minute, data in by_minute.items()
    }
    return [
        mapped.get(
            minute, DashboardDiagnosisTimelineBucket(minute=minute, request_count=0, error_count=0)
        )
        for minute in iter_minute_buckets(from_timestamp, to_timestamp)
    ]


def failures_by_route(
    filters: EventStoreFilters, *, store: DuckDbEventStore | None = None
) -> list[DashboardDiagnosisFailureRouteItem]:
    resolved_store = store if store is not None else get_duckdb_event_store()
    rows = resolved_store.query_events_sql(
        filters,
        select_sql="""
            COALESCE(path, 'unknown') AS path,
            SUM(CASE WHEN type = 'error' OR status_code >= 500 THEN 1 ELSE 0 END) AS failure_count,
            COUNT(*) AS request_count,
            AVG(latency_ms) AS avg_latency_ms
        """,
        suffix_sql=(
            "GROUP BY 1 "
            "HAVING SUM(CASE WHEN type = 'error' OR status_code >= 500 THEN 1 ELSE 0 END) > 0 "
            "ORDER BY 2 DESC LIMIT 20"
        ),
    )
    items = [
        DashboardDiagnosisFailureRouteItem(
            path=str(path),
            failure_count=int(failure_count),
            error_rate=(int(failure_count) / int(request_count)) if int(request_count) else 0.0,
            avg_latency_ms=float(avg_latency_ms or 0.0),
        )
        for path, failure_count, request_count, avg_latency_ms in rows
    ]
    items.sort(key=lambda item: item.failure_count, reverse=True)
    return items


def error_group_events(
    filters: EventStoreFilters,
    *,
    group_key: str,
    limit: int,
    offset: int,
    store: DuckDbEventStore | None = None,
) -> tuple[int, list[DashboardDiagnosisErrorGroupEventItem]]:
    scan_limit = min(MAX_ERROR_GROUP_SCAN_ROWS, max(offset + limit, max(limit * 4, 200)))
    resolved_store = store if store is not None else get_duckdb_event_store()
    rows = resolved_store.fetch_events(
        filters,
        columns=EVENT_SELECT_COLUMNS,
        limit=scan_limit,
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
        _type,
        payload,
    ) in rows:
        payload_dict = payload if isinstance(payload, dict) else {}
        derived = derived_error_group_key(payload_dict, path if isinstance(path, str) else "")
        if derived != group_key:
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
                stack_trace=truncate_diagnosis_text(
                    payload_dict.get("stack_trace"), MAX_DIAGNOSIS_EVENT_STACK_CHARS
                ),
                message=truncate_diagnosis_text(
                    payload_dict.get("exception_message"), MAX_DIAGNOSIS_EVENT_MESSAGE_CHARS
                ),
                exception_type=payload_dict.get("exception_type")
                if isinstance(payload_dict.get("exception_type"), str)
                else None,
            )
        )
    return len(matched), matched[offset : offset + limit]


def error_groups(
    filters: EventStoreFilters, *, limit: int, offset: int, store: DuckDbEventStore | None = None
) -> tuple[int, list[DashboardErrorGroupItem]]:
    scan_limit = min(MAX_ERROR_GROUP_SCAN_ROWS, max(offset + limit, max(limit * 4, 200)))
    resolved_store = store if store is not None else get_duckdb_event_store()
    rows = resolved_store.fetch_events(
        filters,
        columns=EVENT_SELECT_COLUMNS,
        limit=scan_limit,
    )
    grouped: dict[str, dict[str, Any]] = {}
    for (
        event_id,
        timestamp,
        _method,
        path,
        status_code,
        _lat,
        _svc,
        _env,
        _rid,
        _type,
        payload,
    ) in rows:
        payload_dict = payload if isinstance(payload, dict) else {}
        key = derived_error_group_key(payload_dict, path if isinstance(path, str) else "")
        event_time = as_utc_datetime(timestamp)
        current = grouped.get(key)
        if current is None:
            grouped[key] = {
                "count": 1,
                "first_seen": event_time,
                "last_seen": event_time,
                "path": path,
                "exception_type": payload_dict.get("exception_type"),
                "message": payload_dict.get("exception_message"),
                "sample_stack_trace": payload_dict.get("stack_trace"),
                "sample_id": int(event_id),
                "sample_status_code": int(status_code),
            }
            continue
        current["count"] += 1
        current["first_seen"] = min(current["first_seen"], event_time)
        if event_time > current["last_seen"] or (
            event_time == current["last_seen"] and int(event_id) > current["sample_id"]
        ):
            current["last_seen"] = event_time
            current["path"] = path
            current["exception_type"] = payload_dict.get("exception_type")
            current["message"] = payload_dict.get("exception_message")
            current["sample_stack_trace"] = payload_dict.get("stack_trace")
            current["sample_id"] = int(event_id)
            current["sample_status_code"] = int(status_code)
    items: list[DashboardErrorGroupItem] = []
    for key, data in grouped.items():
        exc, msg, stack = error_group_labels(
            data["path"],
            int(data["sample_status_code"]),
            data["exception_type"] if isinstance(data["exception_type"], str) else None,
            data["message"] if isinstance(data["message"], str) else None,
            data["sample_stack_trace"] if isinstance(data["sample_stack_trace"], str) else None,
        )
        items.append(
            DashboardErrorGroupItem(
                group_key=key,
                exception_type=exc,
                message=msg,
                path=data["path"],
                count=int(data["count"]),
                first_seen=data["first_seen"],
                last_seen=data["last_seen"],
                sample_stack_trace=stack,
            )
        )
    items.sort(key=lambda item: (item.last_seen, item.count), reverse=True)
    return len(items), items[offset : offset + limit]


def overview_extended(
    filters: EventStoreFilters,
    *,
    from_timestamp: datetime,
    to_timestamp: datetime,
    store: DuckDbEventStore | None = None,
) -> dict[str, Any]:
    resolved_store = store if store is not None else get_duckdb_event_store()
    error_window_start = to_timestamp - timedelta(minutes=5)
    summary_rows = resolved_store.query_events_sql(
        filters,
        select_sql="""
            quantile_cont(latency_ms, 0.50) AS p50_latency_ms,
            quantile_cont(latency_ms, 0.95) AS p95_latency_ms,
            quantile_cont(latency_ms, 0.99) AS p99_latency_ms,
            AVG(
                CASE
                    WHEN latency_ms <= 300 THEN 1.0
                    WHEN latency_ms <= 1200 THEN 0.5
                    ELSE 0.0
                END
            ) AS apdex_score,
            COUNT(
                DISTINCT COALESCE(
                    json_extract_string(payload, '$.session_id'),
                    json_extract_string(payload, '$.sessionId'),
                    json_extract_string(payload, '$.user_id'),
                    json_extract_string(payload, '$.userId'),
                    json_extract_string(payload, '$.distinct_id'),
                    request_id
                )
            ) AS active_sessions_estimate,
            SUM(
                CASE
                    WHEN status_code >= 500 AND timestamp >= CAST(? AS TIMESTAMP)
                        THEN 1
                    ELSE 0
                END
            ) AS error_burst_count
        """,
        extra_params=[error_window_start.strftime("%Y-%m-%d %H:%M:%S.%f")],
    )
    summary_row = summary_rows[0] if summary_rows else None
    p50_latency_ms = float(summary_row[0] or 0.0) if summary_row else 0.0
    p95_latency_ms = float(summary_row[1] or 0.0) if summary_row else 0.0
    p99_latency_ms = float(summary_row[2] or 0.0) if summary_row else 0.0
    apdex_score = float(summary_row[3] or 1.0) if summary_row else 1.0
    active_sessions_estimate = int(summary_row[4] or 0) if summary_row else 0
    error_burst_count = int(summary_row[5] or 0) if summary_row else 0

    error_type_rows = resolved_store.query_events_sql(
        filters,
        select_sql="""
            CASE
                WHEN lower(
                    COALESCE(json_extract_string(payload, '$.exception_type'), '')
                    || ' ' ||
                    COALESCE(json_extract_string(payload, '$.exception_message'), '')
                ) LIKE '%timeout%'
                OR lower(
                    COALESCE(json_extract_string(payload, '$.exception_type'), '')
                    || ' ' ||
                    COALESCE(json_extract_string(payload, '$.exception_message'), '')
                ) LIKE '%timed out%'
                    THEN 'timeout'
                WHEN lower(
                    COALESCE(json_extract_string(payload, '$.exception_type'), '')
                    || ' ' ||
                    COALESCE(json_extract_string(payload, '$.exception_message'), '')
                ) SIMILAR TO '%(sql|database|db|postgres|mysql|sqlite)%'
                    THEN 'database'
                WHEN lower(
                    COALESCE(json_extract_string(payload, '$.exception_type'), '')
                    || ' ' ||
                    COALESCE(json_extract_string(payload, '$.exception_message'), '')
                ) SIMILAR TO '%(validation|pydantic|invalid)%'
                    THEN 'validation'
                WHEN lower(
                    COALESCE(json_extract_string(payload, '$.exception_type'), '')
                    || ' ' ||
                    COALESCE(json_extract_string(payload, '$.exception_message'), '')
                ) SIMILAR TO '%(network|connection|dns|socket|refused|unreachable)%'
                    THEN 'network'
                WHEN lower(
                    COALESCE(json_extract_string(payload, '$.exception_type'), '')
                    || ' ' ||
                    COALESCE(json_extract_string(payload, '$.exception_message'), '')
                ) SIMILAR TO '%(auth|unauthorized|forbidden|token)%'
                    THEN 'auth'
                ELSE 'server'
            END AS error_type,
            COUNT(*) AS count
        """,
        suffix_sql=(
            "AND (type = 'error' OR status_code >= 500) GROUP BY 1 ORDER BY 2 DESC LIMIT 8"
        ),
    )

    def fetch_breakdown(key_column: str) -> list[dict[str, Any]]:
        rows = resolved_store.query_events_sql(
            filters,
            select_sql=(
                f"COALESCE({key_column}, 'unknown') AS group_key, "
                "COUNT(*) AS request_count, "
                "SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS error_count, "
                "AVG(latency_ms) AS avg_latency_ms"
            ),
            suffix_sql="GROUP BY 1 ORDER BY 3 DESC, 2 DESC LIMIT 8",
        )
        return [
            {
                "key": str(group_key),
                "request_count": int(request_count or 0),
                "error_count": int(error_count or 0),
                "error_rate": (int(error_count or 0) / int(request_count or 0))
                if int(request_count or 0)
                else 0.0,
                "avg_latency_ms": float(avg_latency_ms or 0.0),
            }
            for group_key, request_count, error_count, avg_latency_ms in rows
        ]

    return {
        "p50_latency_ms": p50_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "p99_latency_ms": p99_latency_ms,
        "apdex_score": apdex_score,
        "active_sessions_estimate": active_sessions_estimate,
        "error_burst_count": error_burst_count,
        "active_incident_count": 1 if error_burst_count > 0 else 0,
        "error_type_breakdown": [
            {"error_type": str(error_type), "count": int(count)}
            for error_type, count in error_type_rows
        ],
        "service_breakdown": fetch_breakdown("service_name"),
        "route_breakdown": fetch_breakdown("path"),
    }


def recent_job_failures(
    filters: EventStoreFilters, *, limit: int = 12, store: DuckDbEventStore | None = None
) -> list[dict[str, Any]]:
    """Recent failed background job rows (``type=job``, HTTP status in 5xx range)."""
    resolved_store = store if store is not None else get_duckdb_event_store()
    job_filters = EventStoreFilters(
        project_id=filters.project_id,
        from_timestamp=filters.from_timestamp,
        to_timestamp=filters.to_timestamp,
        exclude_lumonox_traffic=filters.exclude_lumonox_traffic,
        method=filters.method,
        status_class=5,
        path_contains=filters.path_contains,
        environments=filters.environments,
        services=filters.services,
        min_latency_ms=filters.min_latency_ms,
        max_latency_ms=filters.max_latency_ms,
        event_sql_filter=filters.event_sql_filter,
        http_events_only=False,
        require_event_types=("job",),
        include_received_at_in_time_window=filters.include_received_at_in_time_window,
    )
    cap = max(1, min(int(limit), 50))
    rows = resolved_store.fetch_events(
        job_filters,
        columns=(
            "timestamp, method, path, status_code, latency_ms, "
            "service_name, environment, request_id, type, payload"
        ),
        limit=cap,
    )
    items: list[dict[str, Any]] = []
    for (
        timestamp,
        method,
        path,
        status_code,
        latency_ms,
        service_name,
        environment,
        request_id,
        _event_type,
        payload,
    ) in rows:
        cell = dashboard_list_payload_cell(payload)
        trigger = str(method or "").upper() or "JOB"
        job_trigger = cell.get("job_trigger")
        if isinstance(job_trigger, str) and job_trigger.strip():
            trigger = job_trigger.strip()[:32]
        exc_msg = cell.get("exception_message")
        if not isinstance(exc_msg, str) or not exc_msg.strip():
            exc_msg = cell.get("message")
        message = str(exc_msg).strip()[:500] if isinstance(exc_msg, str) else None
        correlated = cell.get("correlated_request_id")
        correlated_request_id = (
            str(correlated).strip()[:128]
            if isinstance(correlated, str) and correlated.strip()
            else None
        )
        rid = str(request_id).strip()[:128] if request_id else None
        items.append(
            {
                "timestamp": as_utc_datetime(timestamp),
                "job_name": str(path or "")[:2048],
                "trigger": trigger,
                "status_code": int(status_code or 0),
                "latency_ms": float(latency_ms or 0.0),
                "service_name": str(service_name or ""),
                "environment": str(environment or ""),
                "message": message,
                "correlated_request_id": correlated_request_id or rid,
            }
        )
    return items
