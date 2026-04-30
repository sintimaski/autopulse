from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from autopulse_backend.dashboard.error_grouping import (
    derived_error_group_key,
    error_group_labels,
)
from autopulse_backend.dashboard.log_query import percentile
from autopulse_backend.dashboard.messages import dashboard_request_log_message
from autopulse_backend.dashboard.parsing import split_csv_values
from autopulse_backend.dashboard.time_window import (
    as_utc_datetime,
    iter_minute_buckets,
    minute_bucket,
)
from autopulse_backend.schemas import (
    DashboardDiagnosisErrorGroupEventItem,
    DashboardDiagnosisFailureRouteItem,
    DashboardDiagnosisTimelineBucket,
    DashboardErrorGroupItem,
    DashboardOverviewBucket,
    DashboardRequestItem,
)
from autopulse_backend.services.event_store import EventStoreFilters, get_duckdb_event_store

EVENT_SELECT_COLUMNS = (
    "id, timestamp, method, path, status_code, latency_ms, "
    "service_name, environment, request_id, type, payload"
)


def build_filters(
    *,
    project_id: UUID,
    from_timestamp: datetime,
    to_timestamp: datetime,
    exclude_autopulse_traffic: bool,
    method: str | None = None,
    status_class: int | None = None,
    path_contains: str | None = None,
    environments: str | None = None,
    services: str | None = None,
    min_latency_ms: float | None = None,
    max_latency_ms: float | None = None,
    event_sql_filter: str | None = None,
) -> EventStoreFilters:
    return EventStoreFilters(
        project_id=project_id,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        exclude_autopulse_traffic=exclude_autopulse_traffic,
        method=method,
        status_class=status_class,
        path_contains=path_contains,
        environments=tuple(split_csv_values(environments)),
        services=tuple(split_csv_values(services)),
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
        event_sql_filter=event_sql_filter,
    )


def request_items(
    filters: EventStoreFilters, *, limit: int, offset: int
) -> tuple[int, list[DashboardRequestItem]]:
    store = get_duckdb_event_store()
    total = store.count_events(filters)
    rows = store.fetch_events(filters, limit=limit, offset=offset)
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
            log_message=dashboard_request_log_message(event_type, payload),
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
        ) in rows
    ]


def overview_series(
    filters: EventStoreFilters, *, from_timestamp: datetime, to_timestamp: datetime
) -> tuple[int, int, float, list[DashboardOverviewBucket]]:
    rows = get_duckdb_event_store().fetch_events(
        filters,
        columns=EVENT_SELECT_COLUMNS,
    )
    buckets: dict[datetime, dict[str, float | int]] = {}
    request_count = 0
    error_count = 0
    latency_total = 0.0
    for (
        _id,
        timestamp,
        *_unused,
        status_code,
        latency_ms,
        _svc,
        _env,
        _req,
        event_type,
        _payload,
    ) in rows:
        request_count += 1
        latency_total += float(latency_ms)
        if event_type == "error" or int(status_code) >= 500:
            error_count += 1
        minute = minute_bucket(timestamp)
        bucket = buckets.setdefault(
            minute,
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
        bucket["request_count"] += 1
        bucket["latency_sum"] += float(latency_ms)
        if event_type == "error" or int(status_code) >= 500:
            bucket["error_count"] += 1
        status_class = int(status_code or 0) // 100
        if status_class == 2:
            bucket["count_2xx"] += 1
        elif status_class == 3:
            bucket["count_3xx"] += 1
        elif status_class == 4:
            bucket["count_4xx"] += 1
        elif status_class == 5:
            bucket["count_5xx"] += 1
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
    filters: EventStoreFilters, *, from_timestamp: datetime, to_timestamp: datetime
) -> list[DashboardDiagnosisTimelineBucket]:
    rows = get_duckdb_event_store().fetch_events(
        filters, columns="id, timestamp, status_code, type", order_by="timestamp ASC, id ASC"
    )
    by_minute: dict[datetime, dict[str, int]] = {}
    for _, timestamp, status_code, event_type in rows:
        minute = minute_bucket(timestamp)
        bucket = by_minute.setdefault(minute, {"request_count": 0, "error_count": 0})
        bucket["request_count"] += 1
        if event_type == "error" or int(status_code) >= 500:
            bucket["error_count"] += 1
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


def failures_by_route(filters: EventStoreFilters) -> list[DashboardDiagnosisFailureRouteItem]:
    rows = get_duckdb_event_store().fetch_events(
        filters, columns="id, path, status_code, latency_ms, type"
    )
    by_route: dict[str, dict[str, float | int]] = {}
    for _, path, status_code, latency_ms, event_type in rows:
        key = str(path or "unknown")
        item = by_route.setdefault(key, {"reqs": 0, "fails": 0, "lat": 0.0})
        item["reqs"] += 1
        item["lat"] += float(latency_ms)
        if event_type == "error" or int(status_code) >= 500:
            item["fails"] += 1
    items = [
        DashboardDiagnosisFailureRouteItem(
            path=path,
            failure_count=int(data["fails"]),
            error_rate=(int(data["fails"]) / int(data["reqs"])) if int(data["reqs"]) else 0.0,
            avg_latency_ms=(float(data["lat"]) / int(data["reqs"])) if int(data["reqs"]) else 0.0,
        )
        for path, data in by_route.items()
        if int(data["fails"]) > 0
    ]
    items.sort(key=lambda i: i.failure_count, reverse=True)
    return items[:20]


def error_group_events(
    filters: EventStoreFilters, *, group_key: str, limit: int, offset: int
) -> tuple[int, list[DashboardDiagnosisErrorGroupEventItem]]:
    rows = get_duckdb_event_store().fetch_events(filters)
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
    return len(matched), matched[offset : offset + limit]


def error_groups(
    filters: EventStoreFilters, *, limit: int, offset: int
) -> tuple[int, list[DashboardErrorGroupItem]]:
    rows = get_duckdb_event_store().fetch_events(filters)
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
    filters: EventStoreFilters, *, from_timestamp: datetime, to_timestamp: datetime
) -> dict[str, Any]:
    rows = get_duckdb_event_store().fetch_events(filters)
    latencies: list[float] = []
    service_stats: dict[str, dict[str, float | int]] = {}
    route_stats: dict[str, dict[str, float | int]] = {}
    error_type_counts: Counter[str] = Counter()
    active_session_keys: set[str] = set()
    error_window_start = to_timestamp - timedelta(minutes=5)
    error_burst_count = 0
    for (
        _id,
        timestamp,
        _method,
        path,
        status_code,
        latency_ms,
        service_name,
        _env,
        request_id,
        event_type,
        payload,
    ) in rows:
        payload_dict = payload if isinstance(payload, dict) else {}
        lat = float(latency_ms)
        latencies.append(lat)
        if int(status_code) >= 500 and as_utc_datetime(timestamp) >= error_window_start:
            error_burst_count += 1
        service_key = str(service_name or "unknown")
        route_key = str(path or "unknown")
        for key, bucket in ((service_key, service_stats), (route_key, route_stats)):
            row = bucket.setdefault(key, {"requests": 0, "errors": 0, "latency_sum": 0.0})
            row["requests"] += 1
            row["errors"] += 1 if int(status_code) >= 500 else 0
            row["latency_sum"] += lat
        if event_type == "error" or int(status_code) >= 500:
            exc = str(payload_dict.get("exception_type") or "")
            msg = str(payload_dict.get("exception_message") or "")
            raw = f"{exc} {msg}".lower()
            if "timeout" in raw or "timed out" in raw:
                error_type_counts["timeout"] += 1
            elif any(
                token in raw for token in ("sql", "database", "db", "postgres", "mysql", "sqlite")
            ):
                error_type_counts["database"] += 1
            elif any(token in raw for token in ("validation", "pydantic", "invalid")):
                error_type_counts["validation"] += 1
            elif any(
                token in raw
                for token in ("network", "connection", "dns", "socket", "refused", "unreachable")
            ):
                error_type_counts["network"] += 1
            elif any(token in raw for token in ("auth", "unauthorized", "forbidden", "token")):
                error_type_counts["auth"] += 1
            else:
                error_type_counts["server"] += 1
        for raw in (
            payload_dict.get("session_id"),
            payload_dict.get("sessionId"),
            payload_dict.get("user_id"),
            payload_dict.get("userId"),
            payload_dict.get("distinct_id"),
        ):
            if isinstance(raw, str) and raw.strip():
                active_session_keys.add(raw.strip())
                break
            if isinstance(raw, int | float) and not isinstance(raw, bool):
                active_session_keys.add(str(int(raw)))
                break
        else:
            if isinstance(request_id, str) and request_id.strip():
                active_session_keys.add(request_id.strip())

    def to_breakdown(source: dict[str, dict[str, float | int]]) -> list[dict[str, Any]]:
        items = []
        for key, data in source.items():
            req = int(data["requests"])
            err = int(data["errors"])
            items.append(
                {
                    "key": key,
                    "request_count": req,
                    "error_count": err,
                    "error_rate": (err / req) if req else 0.0,
                    "avg_latency_ms": (float(data["latency_sum"]) / req) if req else 0.0,
                }
            )
        items.sort(key=lambda row: (row["error_count"], row["request_count"]), reverse=True)
        return items[:8]

    return {
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "apdex_score": _compute_apdex(latencies),
        "active_sessions_estimate": len(active_session_keys),
        "error_burst_count": error_burst_count,
        "active_incident_count": 1 if error_burst_count > 0 else 0,
        "error_type_breakdown": [
            {"error_type": error_type, "count": count}
            for error_type, count in error_type_counts.most_common(8)
        ],
        "service_breakdown": to_breakdown(service_stats),
        "route_breakdown": to_breakdown(route_stats),
    }


def _compute_apdex(latencies: list[float]) -> float:
    total = len(latencies)
    if total == 0:
        return 1.0
    satisfied = sum(1 for latency in latencies if latency <= 300.0)
    tolerated = sum(1 for latency in latencies if 300.0 < latency <= 1200.0)
    return (satisfied + (tolerated / 2.0)) / float(total)
