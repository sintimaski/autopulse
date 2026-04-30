from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import (
    DashboardAuthSession,
    ProjectContext,
    authenticate_dashboard_project,
    require_dashboard_auth_session,
)
from autopulse_backend.dashboard.routes.alert_routes import (
    get_dashboard_alert_capabilities,
    get_dashboard_alert_dispatches,
    get_dashboard_alert_settings,
)
from autopulse_backend.dashboard.routes.auth_routes import (
    get_dashboard_onboarding_status,
    list_dashboard_api_keys,
)
from autopulse_backend.dashboard.routes.diagnosis import (
    get_dashboard_diagnosis_error_group_events,
    get_dashboard_diagnosis_failures_by_route,
    get_dashboard_diagnosis_timeline,
)
from autopulse_backend.dashboard.routes.error_groups import get_dashboard_error_groups
from autopulse_backend.dashboard.routes.overview import (
    get_dashboard_overview,
    get_dashboard_overview_extended,
)
from autopulse_backend.dashboard.routes.requests_routes import get_dashboard_requests
from autopulse_backend.dashboard.routes.ui_settings import (
    get_dashboard_retention_settings,
    get_dashboard_theme_settings,
)
from autopulse_backend.dashboard.routes.widgets import get_dashboard_widgets
from autopulse_backend.database import get_db_session
from autopulse_backend.database.session import get_session_maker
from autopulse_backend.schemas import (
    DashboardBootstrapResponse,
    DashboardDataQueryRequest,
    DashboardDataQueryResponse,
)

router = APIRouter()
BUNDLE_CACHE_TTL_SECONDS = 10.0
BUNDLE_CACHE_MAX_ITEMS = 128
_bundle_cache: OrderedDict[str, tuple[float, DashboardDataQueryResponse]] = OrderedDict()
_bundle_cache_lock = asyncio.Lock()


@router.get("/bootstrap", response_model=DashboardBootstrapResponse)
async def get_dashboard_bootstrap(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardBootstrapResponse:
    retention_settings = await get_dashboard_retention_settings(context=context, session=session)
    alert_settings = await get_dashboard_alert_settings(context=context, session=session)
    theme_settings = await get_dashboard_theme_settings(context=context, session=session)
    api_keys = await list_dashboard_api_keys(auth_session=auth_session, session=session)
    alert_capabilities = await get_dashboard_alert_capabilities()
    onboarding_status = await get_dashboard_onboarding_status(
        auth_session=auth_session, session=session
    )
    return DashboardBootstrapResponse(
        retention_settings=retention_settings,
        alert_settings=alert_settings,
        theme_settings=theme_settings,
        api_keys=api_keys,
        alert_capabilities=alert_capabilities,
        onboarding_status=onboarding_status,
    )


@router.post("/query", response_model=DashboardDataQueryResponse)
async def post_dashboard_query(
    payload: DashboardDataQueryRequest,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardDataQueryResponse:
    _ = session
    scope = payload.scope
    payload_cache_json = json.dumps(
        payload.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":")
    )
    cache_key = f"{context.project_id}:{payload_cache_json}"
    now = monotonic()
    async with _bundle_cache_lock:
        cached = _bundle_cache.get(cache_key)
        if cached is not None and cached[0] > now:
            _bundle_cache.move_to_end(cache_key)
            return cached[1]
        if cached is not None:
            _bundle_cache.pop(cache_key, None)

    session_maker = get_session_maker()

    async def run_with_session(handler):
        async with session_maker() as isolated_session:
            return await handler(isolated_session)

    overview_task = run_with_session(
        lambda isolated_session: get_dashboard_overview(
            context=context,
            session=isolated_session,
            from_timestamp=scope.from_timestamp,
            to_timestamp=scope.to_timestamp,
            window_minutes=scope.window_minutes,
            event_sql_filter=scope.event_sql_filter,
        )
    )
    requests_task = run_with_session(
        lambda isolated_session: get_dashboard_requests(
            context=context,
            session=isolated_session,
            from_timestamp=scope.from_timestamp,
            to_timestamp=scope.to_timestamp,
            window_minutes=scope.window_minutes,
            method=scope.method,
            status_class=scope.status_class,
            path_contains=scope.path_contains,
            environments=scope.environments,
            services=scope.services,
            min_latency_ms=scope.min_latency_ms,
            max_latency_ms=scope.max_latency_ms,
            limit=payload.requests.limit,
            offset=payload.requests.offset,
            event_sql_filter=scope.event_sql_filter,
        )
    )
    overview_extended_task = (
        run_with_session(
            lambda isolated_session: get_dashboard_overview_extended(
                context=context,
                session=isolated_session,
                from_timestamp=scope.from_timestamp,
                to_timestamp=scope.to_timestamp,
                window_minutes=scope.window_minutes,
                event_sql_filter=scope.event_sql_filter,
            )
        )
        if payload.include_extended
        else None
    )
    widgets_task = (
        run_with_session(
            lambda isolated_session: get_dashboard_widgets(
                context=context,
                session=isolated_session,
                from_timestamp=scope.from_timestamp,
                to_timestamp=scope.to_timestamp,
                window_minutes=scope.window_minutes,
            )
        )
        if payload.include_widgets
        else None
    )
    error_groups_task = (
        run_with_session(
            lambda isolated_session: get_dashboard_error_groups(
                context=context,
                session=isolated_session,
                from_timestamp=scope.from_timestamp,
                to_timestamp=scope.to_timestamp,
                window_minutes=scope.window_minutes,
                method=scope.method,
                status_class=scope.status_class,
                path_contains=scope.path_contains,
                environments=scope.environments,
                services=scope.services,
                min_latency_ms=scope.min_latency_ms,
                max_latency_ms=scope.max_latency_ms,
                limit=payload.error_groups.limit,
                offset=payload.error_groups.offset,
                event_sql_filter=scope.event_sql_filter,
            )
        )
        if payload.include_error_groups
        else None
    )
    diagnosis_timeline_task = (
        run_with_session(
            lambda isolated_session: get_dashboard_diagnosis_timeline(
                context=context,
                session=isolated_session,
                from_timestamp=scope.from_timestamp,
                to_timestamp=scope.to_timestamp,
                window_minutes=scope.window_minutes,
                event_sql_filter=scope.event_sql_filter,
            )
        )
        if payload.include_diagnosis
        else None
    )
    diagnosis_failures_task = (
        run_with_session(
            lambda isolated_session: get_dashboard_diagnosis_failures_by_route(
                context=context,
                session=isolated_session,
                from_timestamp=scope.from_timestamp,
                to_timestamp=scope.to_timestamp,
                window_minutes=scope.window_minutes,
                event_sql_filter=scope.event_sql_filter,
            )
        )
        if payload.include_diagnosis
        else None
    )
    diagnosis_error_group_events_task = (
        run_with_session(
            lambda isolated_session: get_dashboard_diagnosis_error_group_events(
                group_key=payload.diagnosis_error_group_key or "",
                context=context,
                session=isolated_session,
                from_timestamp=scope.from_timestamp,
                to_timestamp=scope.to_timestamp,
                window_minutes=scope.window_minutes,
                limit=payload.diagnosis_error_group_events.limit,
                offset=payload.diagnosis_error_group_events.offset,
                event_sql_filter=scope.event_sql_filter,
            )
        )
        if payload.diagnosis_error_group_key
        else None
    )

    alert_dispatches_task = None
    if payload.include_alert_dispatches:
        to_ts = scope.to_timestamp or datetime.now(tz=UTC)
        from_ts = scope.from_timestamp or (to_ts - timedelta(days=7))
        alert_dispatches_task = run_with_session(
            lambda isolated_session: get_dashboard_alert_dispatches(
                context=context,
                session=isolated_session,
                from_timestamp=from_ts,
                to_timestamp=to_ts,
                window_minutes=scope.window_minutes,
                limit=payload.alert_dispatches.limit,
                offset=payload.alert_dispatches.offset,
            )
        )

    optional_tasks = [
        overview_extended_task,
        widgets_task,
        error_groups_task,
        diagnosis_timeline_task,
        diagnosis_failures_task,
        diagnosis_error_group_events_task,
        alert_dispatches_task,
    ]
    overview, requests, *optional_results = await asyncio.gather(
        overview_task,
        requests_task,
        *[task for task in optional_tasks if task is not None],
    )
    optional_iter = iter(optional_results)
    overview_extended = next(optional_iter) if overview_extended_task is not None else None
    widgets = next(optional_iter) if widgets_task is not None else None
    error_groups = next(optional_iter) if error_groups_task is not None else None
    diagnosis_timeline = next(optional_iter) if diagnosis_timeline_task is not None else None
    diagnosis_failures = next(optional_iter) if diagnosis_failures_task is not None else None
    diagnosis_error_group_events = (
        next(optional_iter) if diagnosis_error_group_events_task is not None else None
    )
    alert_dispatches = next(optional_iter) if alert_dispatches_task is not None else None

    response = DashboardDataQueryResponse(
        overview=overview,
        overview_extended=overview_extended,
        widgets=widgets,
        requests=requests,
        error_groups=error_groups,
        diagnosis_timeline=diagnosis_timeline,
        diagnosis_failures=diagnosis_failures,
        diagnosis_error_group_events=diagnosis_error_group_events,
        alert_dispatches=alert_dispatches,
    )
    expires_at = monotonic() + BUNDLE_CACHE_TTL_SECONDS
    async with _bundle_cache_lock:
        _bundle_cache[cache_key] = (expires_at, response)
        _bundle_cache.move_to_end(cache_key)
        while len(_bundle_cache) > BUNDLE_CACHE_MAX_ITEMS:
            _bundle_cache.popitem(last=False)
        stale_keys = [key for key, (exp, _) in _bundle_cache.items() if exp <= monotonic()]
        for key in stale_keys:
            _bundle_cache.pop(key, None)
    return response
