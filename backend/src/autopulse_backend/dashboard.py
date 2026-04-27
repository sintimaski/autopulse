from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import String, case, cast, func, literal, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_backend.alerts import get_or_create_project_alert_settings
from autopulse_backend.auth import (
    ProjectContext,
    authenticate_project,
    authenticate_project_token,
)
from autopulse_backend.config import get_settings
from autopulse_backend.db import get_db_session, get_engine
from autopulse_backend.exclude_autopulse import (
    append_exclude_autopulse_event_filters,
    resolve_exclude_autopulse_traffic,
)
from autopulse_backend.models import (
    AlertDispatch,
    Event,
    ProjectAlertSettings,
    ProjectUiSettings,
)
from autopulse_backend.realtime import project_websocket_hub
from autopulse_backend.schemas import (
    DashboardAlertDispatchesResponse,
    DashboardAlertDispatchItem,
    DashboardAlertSettings,
    DashboardAlertSettingsUpdate,
    DashboardBreakdownItem,
    DashboardDiagnosisErrorGroupEventItem,
    DashboardDiagnosisErrorGroupEventsResponse,
    DashboardDiagnosisFailureRouteItem,
    DashboardDiagnosisFailureRoutesResponse,
    DashboardDiagnosisTimelineBucket,
    DashboardDiagnosisTimelineResponse,
    DashboardErrorGroupItem,
    DashboardErrorGroupsResponse,
    DashboardLogQueryItem,
    DashboardLogQueryPageResponse,
    DashboardLogQueryRequest,
    DashboardLogQueryValidationResponse,
    DashboardOverviewBucket,
    DashboardOverviewExtendedResponse,
    DashboardOverviewResponse,
    DashboardRequestItem,
    DashboardRequestsResponse,
    DashboardRetentionSettings,
    DashboardRetentionSettingsUpdate,
    DashboardThemeSettings,
    DashboardThemeSettingsUpdate,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_FROM_TIMESTAMP_QUERY = Query(default=None)
_TO_TIMESTAMP_QUERY = Query(default=None)
_METHOD_QUERY = Query(default=None)
_STATUS_CLASS_QUERY = Query(default=None, ge=1, le=5)
_PATH_QUERY = Query(default=None)
_ENVIRONMENTS_QUERY = Query(default=None)
_SERVICES_QUERY = Query(default=None)
_LATENCY_MIN_MS_QUERY = Query(default=None, ge=0)
_LATENCY_MAX_MS_QUERY = Query(default=None, ge=0)
_WINDOW_MINUTES_QUERY = Query(default=60, ge=1, le=7 * 24 * 60)
_LIMIT_QUERY = Query(default=50, ge=1, le=200)
_OFFSET_QUERY = Query(default=0, ge=0)
_EVENT_SQL_FILTER_QUERY = Query(default=None, max_length=1500)
_LOG_QUERY_SQL_RE = re.compile(
    r"^\s*select\s+(?P<select>[\w\s,.*]+)\s+from\s+events(?:\s+where\s+(?P<where>.+?))?"
    r"(?:\s+order\s+by\s+(?P<order>[\w_]+)\s*(?P<direction>asc|desc)?)?"
    r"(?:\s+limit\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE,
)
_LOG_QUERY_MAX_LIMIT = 200
_SUPPORTED_SELECT_ALL_COLUMNS = (
    "id,timestamp,method,path,status_code,latency_ms,service_name,environment,request_id"
)
_SUPPORTED_SELECT_ALL_COLUMNS_SPACED = (
    "id, timestamp, method, path, status_code, latency_ms, service_name, environment, request_id"
)


@router.websocket("/updates")
async def dashboard_updates(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing API key")
        return

    session_maker = async_sessionmaker(
        bind=get_engine(), expire_on_commit=False, class_=AsyncSession
    )
    async with session_maker() as session:
        try:
            context = await authenticate_project_token(session=session, token=token)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key")
            return

    await websocket.accept()
    project_websocket_hub.add_connection(project_id=context.project_id, websocket=websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        project_websocket_hub.remove_connection(project_id=context.project_id, websocket=websocket)


def _split_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _serialize_alert_settings(settings: ProjectAlertSettings) -> DashboardAlertSettings:
    return DashboardAlertSettings(
        enabled=settings.enabled,
        destination_email=settings.destination_email,
        error_spike_ratio_threshold=float(settings.error_spike_ratio_threshold),
        error_spike_min_requests=int(settings.error_spike_min_requests),
        error_spike_window_minutes=int(settings.error_spike_window_minutes),
        outage_min_requests=int(settings.outage_min_requests),
        outage_window_minutes=int(settings.outage_window_minutes),
        cooldown_minutes=int(settings.cooldown_minutes),
    )


def _serialize_theme_settings(settings: ProjectUiSettings) -> DashboardThemeSettings:
    theme = (
        settings.theme_preference
        if settings.theme_preference in {"system", "light", "dark"}
        else "system"
    )
    return DashboardThemeSettings(
        theme_preference=theme,
        exclude_autopulse_traffic=bool(settings.exclude_autopulse_traffic),
    )


def _serialize_retention_settings(
    settings: ProjectUiSettings,
    fallback_days: int,
    fallback_query_window_minutes: int,
) -> DashboardRetentionSettings:
    raw_days = (
        int(settings.retention_raw_events_days)
        if settings.retention_raw_events_days
        else fallback_days
    )
    return DashboardRetentionSettings(
        raw_events_days=max(1, raw_days),
        logs_query_max_window_minutes=max(
            1, int(settings.logs_query_max_window_minutes or fallback_query_window_minutes)
        ),
    )


def _as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _get_or_create_project_ui_settings(
    session: AsyncSession,
    project_id,
) -> ProjectUiSettings:
    try:
        settings = await session.scalar(
            select(ProjectUiSettings).where(ProjectUiSettings.project_id == project_id)
        )
    except OperationalError as exc:
        # SQLite local dev path uses create_all and may lag model columns.
        error_text = str(exc)
        if (
            "project_ui_settings.exclude_autopulse_traffic" not in error_text
            and "project_ui_settings.logs_query_max_window_minutes" not in error_text
            and "project_ui_settings.retention_raw_events_days" not in error_text
        ):
            raise
        alter_statements = [
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN exclude_autopulse_traffic BOOLEAN NOT NULL DEFAULT 1",
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN logs_query_max_window_minutes INTEGER NOT NULL DEFAULT 1440",
            "ALTER TABLE project_ui_settings " "ADD COLUMN retention_raw_events_days INTEGER NULL",
        ]
        for statement in alter_statements:
            try:
                await session.execute(text(statement))
            except OperationalError as migration_exc:
                # Column already exists or dialect-specific duplicate-column error.
                duplicate_column_markers = (
                    "duplicate column name",
                    "already exists",
                )
                if not any(
                    marker in str(migration_exc).lower() for marker in duplicate_column_markers
                ):
                    raise
        await session.commit()
        settings = await session.scalar(
            select(ProjectUiSettings).where(ProjectUiSettings.project_id == project_id)
        )
    if settings is not None:
        return settings
    settings = ProjectUiSettings(project_id=project_id, theme_preference="system")
    session.add(settings)
    await session.flush()
    return settings


def _resolve_time_window(
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
    window_minutes: int,
    *,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    resolved_to = _as_utc_datetime(to_timestamp) if to_timestamp is not None else now_utc
    resolved_from = (
        _as_utc_datetime(from_timestamp)
        if from_timestamp is not None
        else resolved_to - timedelta(minutes=window_minutes)
    )
    if resolved_from > resolved_to:
        resolved_from, resolved_to = resolved_to, resolved_from
    return resolved_from, resolved_to


def _minute_bucket(dt: datetime) -> datetime:
    return _as_utc_datetime(dt).replace(second=0, microsecond=0)


def _synthetic_error_key(
    exception_type: str | None,
    exception_message: str | None,
    path: str,
) -> str:
    digest = hashlib.sha256()
    digest.update((exception_type or "").encode("utf-8"))
    digest.update(b"|")
    digest.update((exception_message or "").encode("utf-8"))
    digest.update(b"|")
    digest.update(path.encode("utf-8"))
    return digest.hexdigest()


def _error_group_labels(
    path: str,
    status_code: int,
    exception_type: str | None,
    exception_message: str | None,
    sample_stack_trace: str | None,
) -> tuple[str, str, str | None]:
    """Fill exception/message when ingest omitted SDK fields (e.g. type=error with only status)."""
    exc: str | None = (
        exception_type.strip()
        if isinstance(exception_type, str) and exception_type.strip()
        else None
    )
    msg: str | None = (
        exception_message.strip()
        if isinstance(exception_message, str) and exception_message.strip()
        else None
    )
    stack: str | None = (
        sample_stack_trace.strip()
        if isinstance(sample_stack_trace, str) and sample_stack_trace.strip()
        else None
    )
    if exc is None:
        exc = f"HTTP {status_code}" if status_code else "Error"
    if msg is None:
        msg = (
            f"Request to {path} failed with HTTP {status_code} (no exception payload on ingest)."
            if status_code
            else "No exception metadata was sent with this error event."
        )
    return exc, msg, stack


@dataclass(slots=True)
class _SQLiteErrorGroup:
    group_key: str
    count: int
    first_seen: datetime
    last_seen: datetime
    path: str
    exception_type: str | None
    message: str | None
    sample_stack_trace: str | None
    sample_id: int
    sample_status_code: int


@dataclass(slots=True)
class _ParsedLogQuery:
    normalized_query: str
    where_clauses: list[str]
    order_by: str
    order_desc: bool
    limit: int


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return float(ordered[rank])


def _parse_log_query(query: str) -> _ParsedLogQuery:
    normalized = " ".join(query.strip().split())
    if not normalized:
        raise HTTPException(status_code=422, detail="query must not be empty")
    match = _LOG_QUERY_SQL_RE.match(normalized)
    if not match:
        raise HTTPException(
            status_code=422,
            detail=(
                "Unsupported query syntax. Use: SELECT ... FROM events "
                "WHERE ... ORDER BY timestamp|id ASC|DESC LIMIT n"
            ),
        )

    select_part = (match.group("select") or "").strip().lower()
    if select_part not in {
        "*",
        _SUPPORTED_SELECT_ALL_COLUMNS,
        _SUPPORTED_SELECT_ALL_COLUMNS_SPACED,
    }:
        raise HTTPException(
            status_code=422,
            detail=(
                "Only SELECT * or explicit columns "
                "(id,timestamp,method,path,status_code,latency_ms,service_name,environment,"
                "request_id) "
                "is supported."
            ),
        )

    order_by = (match.group("order") or "timestamp").strip().lower()
    if order_by not in {"timestamp", "id"}:
        raise HTTPException(status_code=422, detail="ORDER BY supports only timestamp or id")
    direction = (match.group("direction") or "desc").strip().lower()
    order_desc = direction != "asc"

    limit_value = int(match.group("limit") or 100)
    limit = max(1, min(limit_value, _LOG_QUERY_MAX_LIMIT))

    where_raw = (match.group("where") or "").strip()
    where_clauses = [
        part.strip()
        for part in re.split(r"\s+and\s+", where_raw, flags=re.IGNORECASE)
        if part.strip()
    ]
    return _ParsedLogQuery(
        normalized_query=normalized,
        where_clauses=where_clauses,
        order_by=order_by,
        order_desc=order_desc,
        limit=limit,
    )


def _decode_log_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    if not cursor:
        return None
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        raw = json.loads(decoded)
        timestamp = _as_utc_datetime(datetime.fromisoformat(str(raw["timestamp"])))
        event_id = int(raw["id"])
        return timestamp, event_id
    except Exception as exc:  # pragma: no cover - defensive parsing
        raise HTTPException(status_code=422, detail="Invalid cursor") from exc


def _encode_log_cursor(timestamp: datetime, event_id: int) -> str:
    payload = {"timestamp": _as_utc_datetime(timestamp).isoformat(), "id": event_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def _apply_log_query_filters(filters: list, where_clauses: list[str]) -> None:
    for clause in where_clauses:
        eq_match = re.match(
            r"^(method|environment|service_name)\s*=\s*'([^']+)'\s*$",
            clause,
            flags=re.IGNORECASE,
        )
        if eq_match:
            field, value = eq_match.groups()
            field_name = field.lower()
            if field_name == "method":
                filters.append(Event.method == value.upper())
            elif field_name == "environment":
                filters.append(Event.environment == value)
            else:
                filters.append(Event.service_name == value)
            continue

        path_like = re.match(r"^path\s+like\s+'([^']+)'\s*$", clause, flags=re.IGNORECASE)
        if path_like:
            filters.append(Event.path.like(path_like.group(1)))
            continue

        status_ge = re.match(r"^status_code\s*>=\s*(\d+)\s*$", clause, flags=re.IGNORECASE)
        if status_ge:
            filters.append(Event.status_code >= int(status_ge.group(1)))
            continue
        status_le = re.match(r"^status_code\s*<=\s*(\d+)\s*$", clause, flags=re.IGNORECASE)
        if status_le:
            filters.append(Event.status_code <= int(status_le.group(1)))
            continue

        latency_ge = re.match(
            r"^latency_ms\s*>=\s*(\d+(?:\.\d+)?)\s*$", clause, flags=re.IGNORECASE
        )
        if latency_ge:
            filters.append(Event.latency_ms >= float(latency_ge.group(1)))
            continue
        latency_le = re.match(
            r"^latency_ms\s*<=\s*(\d+(?:\.\d+)?)\s*$", clause, flags=re.IGNORECASE
        )
        if latency_le:
            filters.append(Event.latency_ms <= float(latency_le.group(1)))
            continue

        raise HTTPException(
            status_code=422,
            detail=f"Unsupported WHERE clause fragment: '{clause}'",
        )


def _append_event_sql_filters(filters: list, event_sql_filter: str | None) -> None:
    """Apply log-query WHERE fragments (AND-separated) to an existing Event filter list."""
    if not event_sql_filter or not event_sql_filter.strip():
        return
    # WHERE fragment is parsed via sqlparse after wrapping; not arbitrary SQL execution.
    wrapped = (
        "SELECT * FROM events WHERE "
        f"{event_sql_filter.strip()} "  # nosec B608
        "ORDER BY timestamp DESC LIMIT 100"
    )
    parsed = _parse_log_query(wrapped)
    _apply_log_query_filters(filters, parsed.where_clauses)


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = _EVENT_SQL_FILTER_QUERY,
) -> DashboardOverviewResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
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
    _append_event_sql_filters(filters, event_sql_filter)

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
    window_minutes = max((resolved_to - resolved_from).total_seconds() / 60.0, 1.0)
    error_rate = (error_total / request_total) if request_total else 0.0
    requests_per_minute = request_total / window_minutes

    dialect_name = session.bind.dialect.name if session.bind is not None else ""
    if dialect_name == "sqlite":
        series_rows = await session.execute(
            select(Event.timestamp, Event.type, Event.status_code, Event.latency_ms).where(*filters)
        )
        buckets: dict[datetime, dict[str, float | int]] = {}
        for timestamp, event_type, status_code, latency_ms in series_rows:
            bucket = _minute_bucket(timestamp)
            current = buckets.setdefault(
                bucket,
                {"request_count": 0, "error_count": 0, "latency_sum": 0.0},
            )
            current["request_count"] += 1
            if event_type == "error" or status_code >= 500:
                current["error_count"] += 1
            current["latency_sum"] += float(latency_ms)
        series = [
            DashboardOverviewBucket(
                minute=bucket,
                request_count=int(data["request_count"]),
                error_count=int(data["error_count"]),
                avg_latency_ms=(
                    float(data["latency_sum"]) / int(data["request_count"])
                    if int(data["request_count"]) > 0
                    else 0.0
                ),
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
            )
            .where(
                *filters,
            )
            .group_by("minute_bucket")
            .order_by("minute_bucket")
        )
        series_result = await session.execute(series_query)
        series = [
            DashboardOverviewBucket(
                minute=_as_utc_datetime(minute_bucket),
                request_count=int(bucket_request_count or 0),
                error_count=int(bucket_error_count or 0),
                avg_latency_ms=float(bucket_avg_latency or 0.0),
            )
            for (
                minute_bucket,
                bucket_request_count,
                bucket_error_count,
                bucket_avg_latency,
            ) in series_result
        ]

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
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = _EVENT_SQL_FILTER_QUERY,
) -> DashboardOverviewExtendedResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
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
    _append_event_sql_filters(filters, event_sql_filter)
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
        if is_error and _as_utc_datetime(timestamp) >= error_window_start:
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
        p50_latency_ms=_percentile(latencies, 0.50),
        p95_latency_ms=_percentile(latencies, 0.95),
        p99_latency_ms=_percentile(latencies, 0.99),
        error_burst_count=error_burst_count,
        active_incident_count=1 if error_burst_count > 0 else 0,
        service_breakdown=to_breakdown(service_stats),
        route_breakdown=to_breakdown(route_stats),
    )


@router.get("/diagnosis/timeline", response_model=DashboardDiagnosisTimelineResponse)
async def get_dashboard_diagnosis_timeline(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = _EVENT_SQL_FILTER_QUERY,
) -> DashboardDiagnosisTimelineResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
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
    _append_event_sql_filters(filters, event_sql_filter)
    rows = await session.execute(select(Event.timestamp, Event.status_code).where(*filters))
    buckets: dict[datetime, dict[str, int]] = {}
    for timestamp, status_code in rows:
        minute = _minute_bucket(timestamp)
        bucket = buckets.setdefault(minute, {"requests": 0, "errors": 0})
        bucket["requests"] += 1
        if int(status_code) >= 500:
            bucket["errors"] += 1
    timeline = [
        DashboardDiagnosisTimelineBucket(
            minute=minute,
            request_count=data["requests"],
            error_count=data["errors"],
        )
        for minute, data in sorted(buckets.items(), key=lambda item: item[0])
    ]
    return DashboardDiagnosisTimelineResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        buckets=timeline,
    )


@router.get("/diagnosis/failures-by-route", response_model=DashboardDiagnosisFailureRoutesResponse)
async def get_dashboard_diagnosis_failures_by_route(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    event_sql_filter: str | None = _EVENT_SQL_FILTER_QUERY,
) -> DashboardDiagnosisFailureRoutesResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
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
    _append_event_sql_filters(filters, event_sql_filter)
    rows = await session.execute(
        select(Event.path, Event.status_code, Event.latency_ms).where(*filters)
    )
    grouped: dict[str, dict[str, float | int]] = {}
    for path, status_code, latency_ms in rows:
        key = path or "unknown"
        item = grouped.setdefault(key, {"requests": 0, "failures": 0, "latency_sum": 0.0})
        item["requests"] += 1
        item["latency_sum"] += float(latency_ms)
        if int(status_code) >= 500:
            item["failures"] += 1
    items = [
        DashboardDiagnosisFailureRouteItem(
            path=path,
            failure_count=int(data["failures"]),
            error_rate=(int(data["failures"]) / int(data["requests"]))
            if int(data["requests"])
            else 0.0,
            avg_latency_ms=(float(data["latency_sum"]) / int(data["requests"]))
            if int(data["requests"])
            else 0.0,
        )
        for path, data in grouped.items()
        if int(data["failures"]) > 0
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
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    limit: int = _LIMIT_QUERY,
    offset: int = _OFFSET_QUERY,
    event_sql_filter: str | None = _EVENT_SQL_FILTER_QUERY,
) -> DashboardDiagnosisErrorGroupEventsResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    _ = server_now
    exclude_autopulse_traffic = await resolve_exclude_autopulse_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        Event.type == "error",
    ]
    append_exclude_autopulse_event_filters(
        filters, exclude_autopulse_traffic=exclude_autopulse_traffic
    )
    _append_event_sql_filters(filters, event_sql_filter)
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
        error_hash = payload_dict.get("error_hash")
        derived_key = (
            str(error_hash)
            if isinstance(error_hash, str) and error_hash
            else _synthetic_error_key(
                payload_dict.get("exception_type")
                if isinstance(payload_dict.get("exception_type"), str)
                else None,
                payload_dict.get("exception_message")
                if isinstance(payload_dict.get("exception_message"), str)
                else None,
                path,
            )
        )
        if derived_key != group_key:
            continue
        matched.append(
            DashboardDiagnosisErrorGroupEventItem(
                id=int(event_id),
                timestamp=_as_utc_datetime(timestamp),
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


@router.get("/requests", response_model=DashboardRequestsResponse)
async def get_dashboard_requests(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    method: str | None = _METHOD_QUERY,
    status_class: int | None = _STATUS_CLASS_QUERY,
    path_contains: str | None = _PATH_QUERY,
    environments: str | None = _ENVIRONMENTS_QUERY,
    services: str | None = _SERVICES_QUERY,
    min_latency_ms: float | None = _LATENCY_MIN_MS_QUERY,
    max_latency_ms: float | None = _LATENCY_MAX_MS_QUERY,
    limit: int = _LIMIT_QUERY,
    offset: int = _OFFSET_QUERY,
    event_sql_filter: str | None = _EVENT_SQL_FILTER_QUERY,
) -> DashboardRequestsResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
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
    if env_values := _split_csv_values(environments):
        filters.append(Event.environment.in_(env_values))
    if service_values := _split_csv_values(services):
        filters.append(Event.service_name.in_(service_values))
    if min_latency_ms is not None:
        filters.append(Event.latency_ms >= min_latency_ms)
    if max_latency_ms is not None:
        filters.append(Event.latency_ms <= max_latency_ms)
    _append_event_sql_filters(filters, event_sql_filter)

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
        )
        .where(*filters)
        .order_by(Event.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    requests_result = await session.execute(requests_query)
    items = [
        DashboardRequestItem(
            timestamp=_as_utc_datetime(timestamp),
            method=event_method,
            path=path,
            status_code=status_code,
            latency_ms=latency_ms,
            service_name=service_name,
            environment=environment,
            request_id=request_id,
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


@router.get("/error-groups", response_model=DashboardErrorGroupsResponse)
async def get_dashboard_error_groups(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    method: str | None = _METHOD_QUERY,
    status_class: int | None = _STATUS_CLASS_QUERY,
    path_contains: str | None = _PATH_QUERY,
    environments: str | None = _ENVIRONMENTS_QUERY,
    services: str | None = _SERVICES_QUERY,
    min_latency_ms: float | None = _LATENCY_MIN_MS_QUERY,
    max_latency_ms: float | None = _LATENCY_MAX_MS_QUERY,
    limit: int = _LIMIT_QUERY,
    offset: int = _OFFSET_QUERY,
    event_sql_filter: str | None = _EVENT_SQL_FILTER_QUERY,
) -> DashboardErrorGroupsResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    exclude_autopulse_traffic = await resolve_exclude_autopulse_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        Event.type == "error",
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
    if env_values := _split_csv_values(environments):
        filters.append(Event.environment.in_(env_values))
    if service_values := _split_csv_values(services):
        filters.append(Event.service_name.in_(service_values))
    if min_latency_ms is not None:
        filters.append(Event.latency_ms >= min_latency_ms)
    if max_latency_ms is not None:
        filters.append(Event.latency_ms <= max_latency_ms)
    _append_event_sql_filters(filters, event_sql_filter)
    dialect_name = session.bind.dialect.name if session.bind is not None else ""

    if dialect_name == "sqlite":
        rows_result = await session.execute(
            select(Event.id, Event.timestamp, Event.path, Event.status_code, Event.payload)
            .where(*filters)
            .order_by(Event.timestamp.desc(), Event.id.desc())
        )
        grouped: dict[str, _SQLiteErrorGroup] = {}
        for event_id, timestamp, path, status_code, payload in rows_result:
            payload_dict = payload if isinstance(payload, dict) else {}
            error_hash = payload_dict.get("error_hash")
            exception_type = payload_dict.get("exception_type")
            exception_message = payload_dict.get("exception_message")
            sample_stack_trace = payload_dict.get("stack_trace")
            if isinstance(error_hash, str) and error_hash:
                group_key = error_hash
            else:
                group_key = _synthetic_error_key(
                    exception_type if isinstance(exception_type, str) else None,
                    exception_message if isinstance(exception_message, str) else None,
                    path,
                )

            current = grouped.get(group_key)
            event_time = _as_utc_datetime(timestamp)
            if current is None:
                grouped[group_key] = _SQLiteErrorGroup(
                    group_key=group_key,
                    count=1,
                    first_seen=event_time,
                    last_seen=event_time,
                    path=path,
                    exception_type=(exception_type if isinstance(exception_type, str) else None),
                    message=exception_message if isinstance(exception_message, str) else None,
                    sample_stack_trace=(
                        sample_stack_trace if isinstance(sample_stack_trace, str) else None
                    ),
                    sample_id=int(event_id),
                    sample_status_code=int(status_code),
                )
                continue

            current.count += 1
            current.first_seen = min(current.first_seen, event_time)
            current.last_seen = max(current.last_seen, event_time)
            if int(event_id) > current.sample_id and event_time == current.last_seen:
                current.sample_id = int(event_id)
                current.path = path
                current.exception_type = exception_type if isinstance(exception_type, str) else None
                current.message = exception_message if isinstance(exception_message, str) else None
                current.sample_stack_trace = (
                    sample_stack_trace if isinstance(sample_stack_trace, str) else None
                )
                current.sample_status_code = int(status_code)

        all_items = []
        for item in grouped.values():
            exc, msg, stack = _error_group_labels(
                item.path,
                item.sample_status_code,
                item.exception_type,
                item.message,
                item.sample_stack_trace,
            )
            all_items.append(
                DashboardErrorGroupItem(
                    group_key=item.group_key,
                    exception_type=exc,
                    message=msg,
                    path=item.path,
                    count=item.count,
                    first_seen=item.first_seen,
                    last_seen=item.last_seen,
                    sample_stack_trace=stack,
                )
            )
        all_items.sort(key=lambda item: (item.last_seen, item.count), reverse=True)
        paged_items = all_items[offset : offset + limit]
        return DashboardErrorGroupsResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            total=len(all_items),
            limit=limit,
            offset=offset,
            items=paged_items,
        )

    error_hash = cast(Event.payload["error_hash"], String)
    exception_type = cast(Event.payload["exception_type"], String)
    exception_message = cast(Event.payload["exception_message"], String)
    stack_trace = cast(Event.payload["stack_trace"], String)
    synthetic_group_key = func.md5(
        func.concat_ws(
            "|",
            func.coalesce(exception_type, ""),
            func.coalesce(exception_message, ""),
            Event.path,
        )
    )
    group_key_expr = func.coalesce(func.nullif(error_hash, ""), synthetic_group_key)

    groups_subquery = (
        select(
            group_key_expr.label("group_key"),
            func.count(Event.id).label("count"),
            func.min(Event.timestamp).label("first_seen"),
            func.max(Event.timestamp).label("last_seen"),
        )
        .where(*filters)
        .group_by(group_key_expr)
        .subquery()
    )
    total_result = await session.execute(select(func.count()).select_from(groups_subquery))
    total = int(total_result.scalar_one())

    samples_subquery = (
        select(
            group_key_expr.label("group_key"),
            Event.path.label("path"),
            Event.status_code.label("status_code"),
            exception_type.label("exception_type"),
            exception_message.label("message"),
            stack_trace.label("sample_stack_trace"),
            func.row_number()
            .over(
                partition_by=group_key_expr,
                order_by=(Event.timestamp.desc(), Event.id.desc()),
            )
            .label("rn"),
        )
        .where(*filters)
        .subquery()
    )

    query = (
        select(
            groups_subquery.c.group_key,
            groups_subquery.c.count,
            groups_subquery.c.first_seen,
            groups_subquery.c.last_seen,
            samples_subquery.c.path,
            samples_subquery.c.status_code,
            samples_subquery.c.exception_type,
            samples_subquery.c.message,
            samples_subquery.c.sample_stack_trace,
        )
        .join(
            samples_subquery,
            (samples_subquery.c.group_key == groups_subquery.c.group_key)
            & (samples_subquery.c.rn == literal(1)),
        )
        .order_by(groups_subquery.c.last_seen.desc(), groups_subquery.c.count.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    items = []
    for (
        group_key,
        count,
        first_seen,
        last_seen,
        sample_path,
        sample_status_code,
        sample_exception_type,
        sample_message,
        sample_stack_trace,
    ) in result:
        exc, msg, stack = _error_group_labels(
            sample_path,
            int(sample_status_code or 0),
            sample_exception_type,
            sample_message,
            sample_stack_trace,
        )
        items.append(
            DashboardErrorGroupItem(
                group_key=group_key,
                exception_type=exc,
                message=msg,
                path=sample_path,
                count=int(count),
                first_seen=_as_utc_datetime(first_seen),
                last_seen=_as_utc_datetime(last_seen),
                sample_stack_trace=stack,
            )
        )
    return DashboardErrorGroupsResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/alert-settings", response_model=DashboardAlertSettings)
async def get_dashboard_alert_settings(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAlertSettings:
    settings = get_settings()
    alert_settings = await get_or_create_project_alert_settings(
        session, context.project_id, settings
    )
    await session.commit()
    await session.refresh(alert_settings)
    return _serialize_alert_settings(alert_settings)


@router.get("/alert-dispatches", response_model=DashboardAlertDispatchesResponse)
async def get_dashboard_alert_dispatches(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    window_minutes: int = _WINDOW_MINUTES_QUERY,
    limit: int = _LIMIT_QUERY,
    offset: int = _OFFSET_QUERY,
) -> DashboardAlertDispatchesResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = _resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    filters = [
        AlertDispatch.project_id == context.project_id,
        AlertDispatch.triggered_at >= resolved_from,
        AlertDispatch.triggered_at <= resolved_to,
    ]
    total_result = await session.execute(select(func.count(AlertDispatch.id)).where(*filters))
    total = int(total_result.scalar_one())
    rows = await session.execute(
        select(AlertDispatch)
        .where(*filters)
        .order_by(AlertDispatch.triggered_at.desc(), AlertDispatch.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        DashboardAlertDispatchItem(
            id=dispatch.id,
            alert_type=dispatch.alert_type,
            destination_email=dispatch.destination_email,
            delivered_via=dispatch.delivered_via,
            triggered_at=_as_utc_datetime(dispatch.triggered_at),
            window_start=_as_utc_datetime(dispatch.window_start),
            window_end=_as_utc_datetime(dispatch.window_end),
            detail=dispatch.detail,
        )
        for dispatch in rows.scalars().all()
    ]
    return DashboardAlertDispatchesResponse(total=total, limit=limit, offset=offset, items=items)


@router.put("/alert-settings", response_model=DashboardAlertSettings)
async def update_dashboard_alert_settings(
    payload: DashboardAlertSettingsUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAlertSettings:
    settings = get_settings()
    alert_settings = await get_or_create_project_alert_settings(
        session, context.project_id, settings
    )
    alert_settings.enabled = payload.enabled
    alert_settings.destination_email = payload.destination_email
    alert_settings.error_spike_ratio_threshold = payload.error_spike_ratio_threshold
    alert_settings.error_spike_min_requests = payload.error_spike_min_requests
    alert_settings.error_spike_window_minutes = payload.error_spike_window_minutes
    alert_settings.outage_min_requests = payload.outage_min_requests
    alert_settings.outage_window_minutes = payload.outage_window_minutes
    alert_settings.cooldown_minutes = payload.cooldown_minutes
    await session.commit()
    await session.refresh(alert_settings)
    return _serialize_alert_settings(alert_settings)


@router.get("/theme-settings", response_model=DashboardThemeSettings)
async def get_dashboard_theme_settings(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardThemeSettings:
    settings = await _get_or_create_project_ui_settings(session, context.project_id)
    await session.commit()
    await session.refresh(settings)
    return _serialize_theme_settings(settings)


@router.put("/theme-settings", response_model=DashboardThemeSettings)
async def update_dashboard_theme_settings(
    payload: DashboardThemeSettingsUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardThemeSettings:
    settings = await _get_or_create_project_ui_settings(session, context.project_id)
    settings.theme_preference = payload.theme_preference
    settings.exclude_autopulse_traffic = payload.exclude_autopulse_traffic
    await session.commit()
    await session.refresh(settings)
    return _serialize_theme_settings(settings)


@router.get("/retention-settings", response_model=DashboardRetentionSettings)
async def get_dashboard_retention_settings(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardRetentionSettings:
    settings = get_settings()
    ui_settings = await _get_or_create_project_ui_settings(session, context.project_id)
    await session.commit()
    await session.refresh(ui_settings)
    return _serialize_retention_settings(
        ui_settings,
        settings.retention_raw_events_days,
        settings.logs_query_max_window_minutes,
    )


@router.put("/retention-settings", response_model=DashboardRetentionSettings)
async def update_dashboard_retention_settings(
    payload: DashboardRetentionSettingsUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardRetentionSettings:
    settings = get_settings()
    ui_settings = await _get_or_create_project_ui_settings(session, context.project_id)
    ui_settings.retention_raw_events_days = payload.raw_events_days
    ui_settings.logs_query_max_window_minutes = payload.logs_query_max_window_minutes
    await session.commit()
    await session.refresh(ui_settings)
    return _serialize_retention_settings(
        ui_settings,
        settings.retention_raw_events_days,
        settings.logs_query_max_window_minutes,
    )


@router.post("/log-query/validate", response_model=DashboardLogQueryValidationResponse)
async def validate_dashboard_log_query(
    payload: DashboardLogQueryRequest,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardLogQueryValidationResponse:
    _ = context
    _ = session
    try:
        parsed = _parse_log_query(payload.query)
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
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardLogQueryPageResponse:
    server_now = datetime.now(tz=UTC)
    settings = get_settings()
    parsed = _parse_log_query(payload.query)
    ui_settings = await _get_or_create_project_ui_settings(session, context.project_id)
    max_minutes = max(
        1,
        int(ui_settings.logs_query_max_window_minutes or settings.logs_query_max_window_minutes),
    )
    resolved_from, resolved_to = _resolve_time_window(
        payload.from_timestamp,
        payload.to_timestamp,
        min(max_minutes, _WINDOW_MINUTES_QUERY.default),
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
    _apply_log_query_filters(filters, parsed.where_clauses)
    cursor = _decode_log_cursor(payload.cursor)
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

    requested_limit = max(1, min(payload.page_size, parsed.limit, _LOG_QUERY_MAX_LIMIT))
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
        next_cursor = _encode_log_cursor(timestamp=last[1], event_id=int(last[0]))
    return DashboardLogQueryPageResponse(
        server_now=server_now,
        query=parsed.normalized_query,
        next_cursor=next_cursor,
        items=[
            DashboardLogQueryItem(
                id=int(event_id),
                timestamp=_as_utc_datetime(timestamp),
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


@router.websocket("/log-query/stream")
async def dashboard_log_query_stream(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing API key")
        return
    session_maker = async_sessionmaker(
        bind=get_engine(), expire_on_commit=False, class_=AsyncSession
    )
    async with session_maker() as session:
        try:
            context = await authenticate_project_token(session=session, token=token)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key")
            return
    await websocket.accept()
    project_websocket_hub.add_connection(project_id=context.project_id, websocket=websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        project_websocket_hub.remove_connection(project_id=context.project_id, websocket=websocket)
