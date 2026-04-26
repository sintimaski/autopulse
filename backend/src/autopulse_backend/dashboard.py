from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_project
from autopulse_backend.db import get_db_session
from autopulse_backend.models import Event
from autopulse_backend.schemas import (
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
