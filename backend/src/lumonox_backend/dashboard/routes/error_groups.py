from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import String, case, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.dashboard.duckdb_queries import build_filters, error_groups
from lumonox_backend.dashboard.error_grouping import (
    DASHBOARD_GROUP_HASH_PATH_SEP,
    SQLiteErrorGroup,
    derived_error_group_key,
    error_group_labels,
    error_like_events_predicate,
)
from lumonox_backend.dashboard.log_query import append_event_sql_filters
from lumonox_backend.dashboard.params import (
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
from lumonox_backend.dashboard.parsing import split_csv_values
from lumonox_backend.dashboard.time_window import as_utc_datetime, resolve_time_window
from lumonox_backend.database import get_db_session
from lumonox_backend.ingestion.exclude_lumonox import (
    append_exclude_lumonox_event_filters,
    resolve_exclude_lumonox_traffic,
)
from lumonox_backend.models import ErrorGroupAggregate, Event
from lumonox_backend.schemas import DashboardErrorGroupItem, DashboardErrorGroupsResponse
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_plane_read_path import resolve_dashboard_read_store
from lumonox_backend.services.event_store import event_store_enabled

router = APIRouter()


@router.get("/error-groups", response_model=DashboardErrorGroupsResponse)
async def get_dashboard_error_groups(
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
) -> DashboardErrorGroupsResponse:
    server_now = datetime.now(tz=UTC)
    resolved_from, resolved_to = resolve_time_window(
        from_timestamp, to_timestamp, window_minutes, now_utc=server_now
    )
    exclude_lumonox_traffic = await resolve_exclude_lumonox_traffic(session, context.project_id)
    filters = [
        Event.project_id == context.project_id,
        Event.timestamp >= resolved_from,
        Event.timestamp <= resolved_to,
        error_like_events_predicate(resolved_from, resolved_to),
    ]
    append_exclude_lumonox_event_filters(filters, exclude_lumonox_traffic=exclude_lumonox_traffic)
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
        read_store = await resolve_dashboard_read_store(
            session=session,
            project_id=context.project_id,
        )
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
            exclude_lumonox_traffic=exclude_lumonox_traffic,
            event_sql_filter=event_sql_filter,
            http_events_only=True,
        )
        total, items = await run_duckdb_read_sync(
            error_groups,
            duckdb_filters,
            limit=limit,
            offset=offset,
            store=read_store,
            duckdb_read_operation="error_groups",
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
    dialect_name = session.bind.dialect.name if session.bind is not None else ""

    has_extended_filters = any(
        value is not None and value != ""
        for value in (
            method,
            status_class,
            path_contains,
            environments,
            services,
            min_latency_ms,
            max_latency_ms,
            event_sql_filter,
        )
    )
    if not exclude_lumonox_traffic and not has_extended_filters:
        total_result = await session.execute(
            select(func.count(ErrorGroupAggregate.id)).where(
                ErrorGroupAggregate.project_id == context.project_id,
                ErrorGroupAggregate.last_seen >= resolved_from,
                ErrorGroupAggregate.last_seen <= resolved_to,
            )
        )
        total = int(total_result.scalar_one() or 0)
        rows = await session.execute(
            select(
                ErrorGroupAggregate.group_key,
                ErrorGroupAggregate.exception_type,
                ErrorGroupAggregate.message,
                ErrorGroupAggregate.path,
                ErrorGroupAggregate.count,
                ErrorGroupAggregate.first_seen,
                ErrorGroupAggregate.last_seen,
                ErrorGroupAggregate.sample_stack_trace,
            )
            .where(
                ErrorGroupAggregate.project_id == context.project_id,
                ErrorGroupAggregate.last_seen >= resolved_from,
                ErrorGroupAggregate.last_seen <= resolved_to,
            )
            .order_by(ErrorGroupAggregate.last_seen.desc(), ErrorGroupAggregate.count.desc())
            .limit(limit)
            .offset(offset)
        )
        items = [
            DashboardErrorGroupItem(
                group_key=group_key,
                exception_type=exception_type,
                message=message,
                path=path,
                count=int(count),
                first_seen=as_utc_datetime(first_seen),
                last_seen=as_utc_datetime(last_seen),
                sample_stack_trace=sample_stack_trace,
            )
            for (
                group_key,
                exception_type,
                message,
                path,
                count,
                first_seen,
                last_seen,
                sample_stack_trace,
            ) in rows
        ]
        return DashboardErrorGroupsResponse(
            server_now=server_now,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            total=total,
            limit=limit,
            offset=offset,
            items=items,
        )

    if dialect_name == "sqlite":
        rows_result = await session.execute(
            select(Event.id, Event.timestamp, Event.path, Event.status_code, Event.payload)
            .where(*filters)
            .order_by(Event.timestamp.desc(), Event.id.desc())
        )
        grouped: dict[str, SQLiteErrorGroup] = {}
        for event_id, timestamp, path, status_code, payload in rows_result:
            payload_dict = payload if isinstance(payload, dict) else {}
            exception_type = payload_dict.get("exception_type")
            exception_message = payload_dict.get("exception_message")
            sample_stack_trace = payload_dict.get("stack_trace")
            route_path = path if isinstance(path, str) else ""
            group_key = derived_error_group_key(payload_dict, route_path)

            current = grouped.get(group_key)
            event_time = as_utc_datetime(timestamp)
            if current is None:
                grouped[group_key] = SQLiteErrorGroup(
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
            exc, msg, stack = error_group_labels(
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
    error_hash_trimmed = func.nullif(func.trim(error_hash), "")
    group_key_expr = case(
        (
            error_hash_trimmed.isnot(None),
            func.concat(
                error_hash_trimmed,
                literal(DASHBOARD_GROUP_HASH_PATH_SEP),
                func.coalesce(Event.path, literal("")),
            ),
        ),
        else_=synthetic_group_key,
    )

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
        exc, msg, stack = error_group_labels(
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
                first_seen=as_utc_datetime(first_seen),
                last_seen=as_utc_datetime(last_seen),
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
