"""Dashboard reads for background job / cron failure rows."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext
from autopulse_backend.dashboard.duckdb_queries import build_filters, recent_job_failures
from autopulse_backend.dashboard.log_query import append_event_sql_filters
from autopulse_backend.dashboard.parsing import split_csv_values
from autopulse_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from autopulse_backend.ingestion.exclude_autopulse import (
    append_exclude_autopulse_event_filters,
    resolve_exclude_autopulse_traffic,
)
from autopulse_backend.models import Event
from autopulse_backend.schemas import (
    DashboardRecentJobFailureItem,
    DashboardRecentJobFailuresResponse,
)
from autopulse_backend.services.duckdb_async import run_duckdb_read_sync
from autopulse_backend.services.event_plane_read_path import resolve_dashboard_read_store
from autopulse_backend.services.event_store import event_store_enabled


async def get_dashboard_recent_job_failures(
    *,
    context: ProjectContext,
    session: AsyncSession,
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
    window_minutes: int,
    path_contains: str | None,
    environments: str | None,
    services: str | None,
    min_latency_ms: float | None,
    max_latency_ms: float | None,
    event_sql_filter: str | None,
    limit: int = 12,
) -> DashboardRecentJobFailuresResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    exclude_autopulse_traffic = await resolve_exclude_autopulse_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        Event.type == "job",
        Event.status_code >= 500,
    ]
    append_exclude_autopulse_event_filters(
        filters, exclude_autopulse_traffic=exclude_autopulse_traffic
    )
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
            path_contains=path_contains,
            environments=environments,
            services=services,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            exclude_autopulse_traffic=exclude_autopulse_traffic,
            event_sql_filter=event_sql_filter,
        )
        raw = await run_duckdb_read_sync(
            recent_job_failures, duckdb_filters, limit=limit, store=read_store
        )
        duckdb_items = [
            DashboardRecentJobFailureItem(
                timestamp=row["timestamp"],
                job_name=row["job_name"],
                trigger=row["trigger"],
                status_code=int(row["status_code"]),
                latency_ms=float(row["latency_ms"]),
                service_name=row["service_name"],
                environment=row["environment"],
                message=row.get("message"),
                correlated_request_id=row.get("correlated_request_id"),
            )
            for row in raw
        ]
        return DashboardRecentJobFailuresResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            items=duckdb_items,
        )

    rows = await session.execute(
        select(
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
        .order_by(Event.timestamp.desc())
        .limit(max(1, min(int(limit), 50)))
    )
    items: list[DashboardRecentJobFailureItem] = []
    for (
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
        cell = payload if isinstance(payload, dict) else {}
        trigger = str(method or "").upper() or "JOB"
        jt = cell.get("job_trigger")
        if isinstance(jt, str) and jt.strip():
            trigger = jt.strip()[:32]
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
            DashboardRecentJobFailureItem(
                timestamp=as_utc_datetime(timestamp),
                job_name=str(path or "")[:2048],
                trigger=trigger,
                status_code=int(status_code or 0),
                latency_ms=float(latency_ms or 0.0),
                service_name=str(service_name or ""),
                environment=str(environment or ""),
                message=message,
                correlated_request_id=correlated_request_id or rid,
            )
        )
    return DashboardRecentJobFailuresResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        items=items,
    )
