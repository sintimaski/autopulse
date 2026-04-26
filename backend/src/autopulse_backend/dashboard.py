from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, case, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_project
from autopulse_backend.db import get_db_session
from autopulse_backend.models import Event
from autopulse_backend.schemas import (
    DashboardErrorGroupItem,
    DashboardErrorGroupsResponse,
    DashboardOverviewBucket,
    DashboardOverviewResponse,
    DashboardRequestItem,
    DashboardRequestsResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_FROM_TIMESTAMP_QUERY = Query(default=None)
_TO_TIMESTAMP_QUERY = Query(default=None)
_METHOD_QUERY = Query(default=None)
_STATUS_CLASS_QUERY = Query(default=None, ge=1, le=5)
_LIMIT_QUERY = Query(default=50, ge=1, le=200)
_OFFSET_QUERY = Query(default=0, ge=0)


def _resolve_time_window(
    from_timestamp: datetime | None, to_timestamp: datetime | None
) -> tuple[datetime, datetime]:
    now_utc = datetime.now(tz=UTC)
    resolved_to = to_timestamp.astimezone(UTC) if to_timestamp is not None else now_utc
    resolved_from = (
        from_timestamp.astimezone(UTC)
        if from_timestamp is not None
        else resolved_to - timedelta(minutes=60)
    )
    if resolved_from > resolved_to:
        resolved_from, resolved_to = resolved_to, resolved_from
    return resolved_from, resolved_to


def _minute_bucket(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(second=0, microsecond=0)


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


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
) -> DashboardOverviewResponse:
    resolved_from, resolved_to = _resolve_time_window(from_timestamp, to_timestamp)
    error_condition = (Event.type == "error") | (Event.status_code >= 500)

    totals_query = select(
        func.count(Event.id),
        func.sum(case((error_condition, 1), else_=0)),
        func.avg(Event.latency_ms),
    ).where(
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
    )
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
            select(Event.timestamp, Event.type, Event.status_code, Event.latency_ms).where(
                Event.project_id == context.project_id,
                Event.timestamp >= resolved_from,
                Event.timestamp <= resolved_to,
            )
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
                Event.project_id == context.project_id,
                Event.timestamp >= resolved_from,
                Event.timestamp <= resolved_to,
            )
            .group_by("minute_bucket")
            .order_by("minute_bucket")
        )
        series_result = await session.execute(series_query)
        series = [
            DashboardOverviewBucket(
                minute=minute_bucket.astimezone(UTC),
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
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        request_count=request_total,
        error_count=error_total,
        error_rate=error_rate,
        avg_latency_ms=avg_latency_ms,
        requests_per_minute=requests_per_minute,
        series=series,
    )


@router.get("/requests", response_model=DashboardRequestsResponse)
async def get_dashboard_requests(
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_timestamp: datetime | None = _FROM_TIMESTAMP_QUERY,
    to_timestamp: datetime | None = _TO_TIMESTAMP_QUERY,
    method: str | None = _METHOD_QUERY,
    status_class: int | None = _STATUS_CLASS_QUERY,
    limit: int = _LIMIT_QUERY,
    offset: int = _OFFSET_QUERY,
) -> DashboardRequestsResponse:
    resolved_from, resolved_to = _resolve_time_window(from_timestamp, to_timestamp)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
    ]
    if method:
        filters.append(Event.method == method.upper())
    if status_class is not None:
        lower = status_class * 100
        filters.extend([Event.status_code >= lower, Event.status_code < lower + 100])

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
            timestamp=timestamp.astimezone(UTC),
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
    limit: int = _LIMIT_QUERY,
    offset: int = _OFFSET_QUERY,
) -> DashboardErrorGroupsResponse:
    resolved_from, resolved_to = _resolve_time_window(from_timestamp, to_timestamp)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        Event.type == "error",
    ]
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
            event_time = timestamp.astimezone(UTC)
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
                first_seen=first_seen.astimezone(UTC),
                last_seen=last_seen.astimezone(UTC),
                sample_stack_trace=stack,
            )
        )
    return DashboardErrorGroupsResponse(
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )
