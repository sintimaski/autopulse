from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_dashboard_project
from autopulse_backend.core.config import get_settings
from autopulse_backend.dashboard.duckdb_queries import build_filters
from autopulse_backend.dashboard.params import DEFAULT_WINDOW_MINUTES
from autopulse_backend.dashboard.read_rate_limit import enforce_dashboard_read_rate_limit
from autopulse_backend.dashboard.repositories.project_ui import get_or_create_project_ui_settings
from autopulse_backend.dashboard.time_window import resolve_time_window
from autopulse_backend.database import get_db_session
from autopulse_backend.schemas import DashboardQueryExplorerRequest, DashboardQueryExplorerResponse
from autopulse_backend.services.duckdb_async import run_duckdb_read_sync
from autopulse_backend.services.event_plane_read_path import resolve_dashboard_read_store
from autopulse_backend.services.event_store import event_store_enabled

router = APIRouter()

_FORBIDDEN_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|install|load|export|import)\b",
    re.IGNORECASE,
)


def _validate_query(raw: str) -> str:
    query = raw.strip().rstrip(";").strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")
    lowered = query.lower()
    # Allow newline/indent after SELECT or WITH (not only "select " / "with ").
    if not re.match(r"^(select|with)\b", lowered):
        raise HTTPException(status_code=422, detail="Query explorer only allows SELECT/CTE queries")
    if _FORBIDDEN_SQL_RE.search(lowered):
        raise HTTPException(status_code=422, detail="Query contains forbidden SQL keywords")
    if "scoped_events" not in lowered:
        raise HTTPException(
            status_code=422,
            detail="Query must read from scoped_events (project/time scoped view).",
        )
    without_scoped = re.sub(r"\bscoped_events\b", "", lowered)
    if re.search(r"\bevents\b", without_scoped) or "dashboard_widget_points" in without_scoped:
        raise HTTPException(
            status_code=422,
            detail="Query explorer only allows reads from scoped_events.",
        )
    return query


def _to_json_safe(value: object) -> object:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC).isoformat()
        return value.astimezone(UTC).isoformat()
    return value


@router.post("/query-explorer/execute", response_model=DashboardQueryExplorerResponse)
async def execute_dashboard_query_explorer(
    payload: DashboardQueryExplorerRequest,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardQueryExplorerResponse:
    settings = get_settings()
    enforce_dashboard_read_rate_limit(
        settings=settings,
        project_id=context.project_id,
        endpoint="query_explorer",
    )
    if not event_store_enabled():
        raise HTTPException(
            status_code=400,
            detail="Query explorer currently requires DuckDB event store.",
        )
    query = _validate_query(payload.query)
    server_now = datetime.now(tz=UTC)
    ui_settings = await get_or_create_project_ui_settings(session, context.project_id)
    project_wide = payload.scope_mode == "project_wide"
    if project_wide:
        resolved_from = datetime(1970, 1, 1, tzinfo=UTC)
        resolved_to = server_now
        filters = build_filters(
            project_id=context.project_id,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            exclude_autopulse_traffic=bool(ui_settings.exclude_autopulse_traffic),
            http_events_only=False,
            skip_timestamp_filter=True,
        )
    else:
        max_minutes = max(
            1,
            int(
                ui_settings.logs_query_max_window_minutes or settings.logs_query_max_window_minutes
            ),
        )
        resolved_from, resolved_to = resolve_time_window(
            payload.from_timestamp,
            payload.to_timestamp,
            min(max_minutes, payload.window_minutes or DEFAULT_WINDOW_MINUTES),
            now_utc=server_now,
        )
        if (resolved_to - resolved_from) > timedelta(minutes=max_minutes):
            resolved_from = resolved_to - timedelta(minutes=max_minutes)
        filters = build_filters(
            project_id=context.project_id,
            from_timestamp=resolved_from,
            to_timestamp=resolved_to,
            method=payload.method,
            status_class=payload.status_class,
            path_contains=payload.path_contains,
            environments=payload.environments,
            services=payload.services,
            min_latency_ms=payload.min_latency_ms,
            max_latency_ms=payload.max_latency_ms,
            exclude_autopulse_traffic=bool(ui_settings.exclude_autopulse_traffic),
            event_sql_filter=payload.event_sql_filter,
            http_events_only=False,
        )
    store = await resolve_dashboard_read_store(
        session=session,
        project_id=context.project_id,
        settings=settings,
    )
    columns, rows = await run_duckdb_read_sync(
        store.query_scoped_events_sql,
        filters,
        query,
        payload.row_limit + 1,
    )
    truncated = len(rows) > payload.row_limit
    selected_rows = rows[: payload.row_limit]
    safe_rows: list[list[Any]] = [[_to_json_safe(value) for value in row] for row in selected_rows]
    return DashboardQueryExplorerResponse(
        server_now=server_now,
        from_timestamp=resolved_from,
        to_timestamp=resolved_to,
        query=query,
        columns=columns,
        rows=safe_rows,
        truncated=truncated,
    )
