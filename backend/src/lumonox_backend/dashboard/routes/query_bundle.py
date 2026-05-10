from __future__ import annotations

import asyncio
import json
import os
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import (
    DashboardAuthSession,
    ProjectContext,
    authenticate_dashboard_project,
    require_dashboard_auth_session,
)
from lumonox_backend.core.config import get_settings
from lumonox_backend.dashboard.read_rate_limit import enforce_dashboard_read_rate_limit
from lumonox_backend.dashboard.routes.alert_routes import (
    get_dashboard_alert_capabilities,
    get_dashboard_alert_dispatches,
    get_dashboard_alert_settings,
)
from lumonox_backend.dashboard.routes.auth_routes import (
    get_dashboard_onboarding_status,
    list_dashboard_api_keys,
)
from lumonox_backend.dashboard.routes.diagnosis import (
    get_dashboard_diagnosis_error_group_events,
    get_dashboard_diagnosis_failures_by_route,
    get_dashboard_diagnosis_timeline,
)
from lumonox_backend.dashboard.routes.error_groups import get_dashboard_error_groups
from lumonox_backend.dashboard.routes.job_events import get_dashboard_recent_job_failures
from lumonox_backend.dashboard.routes.overview import (
    get_dashboard_overview,
    get_dashboard_overview_extended,
)
from lumonox_backend.dashboard.routes.requests_routes import get_dashboard_requests
from lumonox_backend.dashboard.routes.ui_settings import (
    get_dashboard_retention_settings,
    get_dashboard_theme_settings,
)
from lumonox_backend.dashboard.routes.widgets import get_dashboard_widgets
from lumonox_backend.database import get_db_session
from lumonox_backend.database.session import get_session_maker
from lumonox_backend.metrics import service_metrics
from lumonox_backend.schemas import (
    DashboardBootstrapResponse,
    DashboardDataQueryRequest,
    DashboardDataQueryResponse,
)

router = APIRouter()


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        parsed = float(str(raw).strip())
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        parsed = int(str(raw).strip())
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


# Light = default overview+requests bundle; heavy = extended/widgets/diagnosis slices.
# Env names match common deployments (see backend/.env examples).
BUNDLE_LIGHT_CACHE_TTL_SECONDS = _env_float(
    "LUMONOX_DASHBOARD_QUERY_CACHE_TTL_SECONDS",
    1.25,
    minimum=0.05,
    maximum=120.0,
)
BUNDLE_HEAVY_CACHE_TTL_SECONDS = _env_float(
    "LUMONOX_DASHBOARD_QUERY_CACHE_STALE_TTL_SECONDS",
    1.0,
    minimum=0.05,
    maximum=120.0,
)
BUNDLE_CACHE_MAX_ITEMS = 128
_bundle_cache: OrderedDict[str, tuple[float, DashboardDataQueryResponse]] = OrderedDict()
_bundle_cache_lock = asyncio.Lock()
_bundle_inflight: dict[str, asyncio.Task[DashboardDataQueryResponse]] = {}
_bundle_inflight_lock = asyncio.Lock()
_bundle_light_concurrency = asyncio.Semaphore(
    _env_int("LUMONOX_DASHBOARD_QUERY_LIGHT_CONCURRENCY", 8, minimum=1, maximum=64)
)


def _default_heavy_query_concurrency() -> int:
    cpu = os.cpu_count() or 4
    return max(2, min(8, int(cpu)))


def _dedupe_use_shield() -> bool:
    raw = os.getenv("LUMONOX_DASHBOARD_QUERY_DEDUPE_USE_SHIELD", "1")
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _resolve_dashboard_heavy_query_concurrency() -> int:
    """Cap concurrent heavy `/dashboard/query` bundles (extended/widgets/diagnosis slices).

    Heavy work fans out several DuckDB reads; starving this semaphore queues requests
    until clients abort. Prefer ``LUMONOX_DASHBOARD_QUERY_HEAVY_CONCURRENCY``; the
    legacy ``LUMONOX_DASHBOARD_QUERY_PRESSURE_INFLIGHT_THRESHOLD`` is still honored
    when the new name is unset.
    """
    heavy = os.getenv("LUMONOX_DASHBOARD_QUERY_HEAVY_CONCURRENCY")
    if heavy is not None and str(heavy).strip():
        return _env_int(
            "LUMONOX_DASHBOARD_QUERY_HEAVY_CONCURRENCY",
            _default_heavy_query_concurrency(),
            minimum=1,
            maximum=32,
        )
    legacy = os.getenv("LUMONOX_DASHBOARD_QUERY_PRESSURE_INFLIGHT_THRESHOLD")
    if legacy is not None and str(legacy).strip():
        return _env_int(
            "LUMONOX_DASHBOARD_QUERY_PRESSURE_INFLIGHT_THRESHOLD",
            2,
            minimum=1,
            maximum=32,
        )
    return _default_heavy_query_concurrency()


_bundle_heavy_concurrency = asyncio.Semaphore(_resolve_dashboard_heavy_query_concurrency())
_bundle_version_meta_lock = asyncio.Lock()
_bundle_project_version_locks: dict[str, asyncio.Lock] = {}
_bundle_project_versions: dict[str, int] = {}


def _project_version_key(project_id: UUID) -> str:
    return str(project_id)


async def _async_lock_for_project_version(project_id: UUID) -> asyncio.Lock:
    """Return a per-project lock so high ingest on project A does not serialize B's reads."""
    key = _project_version_key(project_id)
    lock = _bundle_project_version_locks.get(key)
    if lock is not None:
        return lock
    async with _bundle_version_meta_lock:
        lock = _bundle_project_version_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _bundle_project_version_locks[key] = lock
        return lock


async def mark_project_dashboard_dirty(project_id: UUID) -> int:
    """Increment the cache version used for bundle cache keys.

    Ingest/retention paths call this after durable writes so subsequent reads
    skip stale cached responses without needing to sweep every cache key.
    """

    key = _project_version_key(project_id)
    lock = await _async_lock_for_project_version(project_id)
    async with lock:
        current = _bundle_project_versions.get(key, 0) + 1
        _bundle_project_versions[key] = current
        return current


async def get_project_dashboard_version(project_id: UUID) -> int:
    key = _project_version_key(project_id)
    lock = await _async_lock_for_project_version(project_id)
    async with lock:
        return _bundle_project_versions.get(key, 0)


def _select_bundle_tier(payload: DashboardDataQueryRequest) -> Literal["light", "heavy"]:
    if (
        payload.include_extended
        or payload.include_widgets
        or payload.include_error_groups
        or payload.include_diagnosis
        or payload.include_recent_job_failures
        or payload.include_alert_dispatches
        or bool(payload.diagnosis_error_group_key)
    ):
        return "heavy"
    return "light"


def _bundle_ttl_seconds(payload: DashboardDataQueryRequest) -> float:
    return (
        BUNDLE_HEAVY_CACHE_TTL_SECONDS
        if _select_bundle_tier(payload) == "heavy"
        else BUNDLE_LIGHT_CACHE_TTL_SECONDS
    )


def _bundle_semaphore(payload: DashboardDataQueryRequest) -> asyncio.Semaphore:
    if _select_bundle_tier(payload) == "heavy":
        return _bundle_heavy_concurrency
    return _bundle_light_concurrency


async def _read_cached_bundle_response(cache_key: str) -> DashboardDataQueryResponse | None:
    now = monotonic()
    async with _bundle_cache_lock:
        cached = _bundle_cache.get(cache_key)
        if cached is not None and cached[0] > now:
            _bundle_cache.move_to_end(cache_key)
            return cached[1]
        if cached is not None:
            _bundle_cache.pop(cache_key, None)
    return None


async def _cache_bundle_response(
    *, cache_key: str, payload: DashboardDataQueryRequest, response: DashboardDataQueryResponse
) -> None:
    expires_at = monotonic() + _bundle_ttl_seconds(payload)
    async with _bundle_cache_lock:
        _bundle_cache[cache_key] = (expires_at, response)
        _bundle_cache.move_to_end(cache_key)
        while len(_bundle_cache) > BUNDLE_CACHE_MAX_ITEMS:
            _bundle_cache.popitem(last=False)
        now = monotonic()
        stale_keys = [key for key, (exp, _) in _bundle_cache.items() if exp <= now]
        for key in stale_keys:
            _bundle_cache.pop(key, None)


async def _compute_bundle_with_inflight_dedupe(
    *,
    cache_key: str,
    payload: DashboardDataQueryRequest,
    context: ProjectContext,
) -> DashboardDataQueryResponse:
    async with _bundle_inflight_lock:
        existing = _bundle_inflight.get(cache_key)
        if existing is not None:
            return await asyncio.shield(existing) if _dedupe_use_shield() else await existing
        task = asyncio.create_task(_run_bundle_query(payload=payload, context=context))
        _bundle_inflight[cache_key] = task
    try:
        response = await asyncio.shield(task) if _dedupe_use_shield() else await task
        await _cache_bundle_response(cache_key=cache_key, payload=payload, response=response)
        return response
    finally:
        async with _bundle_inflight_lock:
            current = _bundle_inflight.get(cache_key)
            if current is task:
                _bundle_inflight.pop(cache_key, None)


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
    alert_capabilities = await get_dashboard_alert_capabilities(context=context, session=session)
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
    tier = _select_bundle_tier(payload)
    bundle_started = monotonic()
    try:
        enforce_dashboard_read_rate_limit(
            settings=get_settings(),
            project_id=context.project_id,
            endpoint="query_bundle",
        )
        version = await get_project_dashboard_version(context.project_id)
        payload_cache_json = json.dumps(
            payload.model_dump(mode="json", exclude_none=True),
            sort_keys=True,
            separators=(",", ":"),
        )
        cache_key = f"{context.project_id}:{version}:{payload_cache_json}"
        cached = await _read_cached_bundle_response(cache_key)
        if cached is not None:
            return cached
        semaphore = _bundle_semaphore(payload)
        async with semaphore:
            cached = await _read_cached_bundle_response(cache_key)
            if cached is not None:
                return cached
            return await _compute_bundle_with_inflight_dedupe(
                cache_key=cache_key,
                payload=payload,
                context=context,
            )
    except asyncio.CancelledError:
        with suppress(Exception):
            service_metrics.increment("dashboard.query.cancelled_total")
            service_metrics.increment(f"dashboard.query.{tier}.cancelled_total")
        raise
    finally:
        elapsed_ms = int((monotonic() - bundle_started) * 1000)
        with suppress(Exception):
            service_metrics.increment(
                f"dashboard.query.{tier}.duration_ms", amount=max(0, elapsed_ms)
            )
            service_metrics.increment(f"dashboard.query.{tier}.total")
            slow_cutoff = 3000 if tier == "heavy" else 1000
            if elapsed_ms >= slow_cutoff:
                service_metrics.increment(f"dashboard.query.{tier}.slow_total")


async def _timed_dashboard_slice(slice_name: str, awaitable: Awaitable[Any]) -> Any:
    started = monotonic()
    try:
        return await awaitable
    finally:
        with suppress(Exception):
            service_metrics.increment(
                f"dashboard.query.slice.{slice_name}.duration_ms",
                amount=int((monotonic() - started) * 1000),
            )


async def _run_bundle_query(
    *, payload: DashboardDataQueryRequest, context: ProjectContext
) -> DashboardDataQueryResponse:
    scope = payload.scope
    session_maker = get_session_maker()

    async def run_with_session(
        handler: Callable[[AsyncSession], Awaitable[Any]],
    ) -> Any:
        async with session_maker() as isolated_session:
            return await handler(isolated_session)

    overview_task = _timed_dashboard_slice(
        "overview",
        run_with_session(
            lambda isolated_session: get_dashboard_overview(
                context=context,
                session=isolated_session,
                from_timestamp=scope.from_timestamp,
                to_timestamp=scope.to_timestamp,
                window_minutes=scope.window_minutes,
                event_sql_filter=scope.event_sql_filter,
            ),
        ),
    )
    requests_task = _timed_dashboard_slice(
        "requests",
        run_with_session(
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
            ),
        ),
    )
    overview_extended_task = (
        _timed_dashboard_slice(
            "overview_extended",
            run_with_session(
                lambda isolated_session: get_dashboard_overview_extended(
                    context=context,
                    session=isolated_session,
                    from_timestamp=scope.from_timestamp,
                    to_timestamp=scope.to_timestamp,
                    window_minutes=scope.window_minutes,
                    event_sql_filter=scope.event_sql_filter,
                ),
            ),
        )
        if payload.include_extended
        else None
    )
    widgets_task = (
        _timed_dashboard_slice(
            "widgets",
            run_with_session(
                lambda isolated_session: get_dashboard_widgets(
                    context=context,
                    session=isolated_session,
                    from_timestamp=scope.from_timestamp,
                    to_timestamp=scope.to_timestamp,
                    window_minutes=scope.window_minutes,
                ),
            ),
        )
        if payload.include_widgets
        else None
    )
    error_groups_task = (
        _timed_dashboard_slice(
            "error_groups",
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
                ),
            ),
        )
        if payload.include_error_groups
        else None
    )
    diagnosis_timeline_task = (
        _timed_dashboard_slice(
            "diagnosis_timeline",
            run_with_session(
                lambda isolated_session: get_dashboard_diagnosis_timeline(
                    context=context,
                    session=isolated_session,
                    from_timestamp=scope.from_timestamp,
                    to_timestamp=scope.to_timestamp,
                    window_minutes=scope.window_minutes,
                    event_sql_filter=scope.event_sql_filter,
                ),
            ),
        )
        if payload.include_diagnosis
        else None
    )
    diagnosis_failures_task = (
        _timed_dashboard_slice(
            "diagnosis_failures",
            run_with_session(
                lambda isolated_session: get_dashboard_diagnosis_failures_by_route(
                    context=context,
                    session=isolated_session,
                    from_timestamp=scope.from_timestamp,
                    to_timestamp=scope.to_timestamp,
                    window_minutes=scope.window_minutes,
                    event_sql_filter=scope.event_sql_filter,
                ),
            ),
        )
        if payload.include_diagnosis
        else None
    )
    recent_job_failures_task = (
        _timed_dashboard_slice(
            "recent_job_failures",
            run_with_session(
                lambda isolated_session: get_dashboard_recent_job_failures(
                    context=context,
                    session=isolated_session,
                    from_timestamp=scope.from_timestamp,
                    to_timestamp=scope.to_timestamp,
                    window_minutes=scope.window_minutes,
                    path_contains=scope.path_contains,
                    environments=scope.environments,
                    services=scope.services,
                    min_latency_ms=scope.min_latency_ms,
                    max_latency_ms=scope.max_latency_ms,
                    event_sql_filter=scope.event_sql_filter,
                ),
            ),
        )
        if payload.include_recent_job_failures
        else None
    )
    diagnosis_error_group_events_task = (
        _timed_dashboard_slice(
            "diagnosis_error_group_events",
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
                ),
            ),
        )
        if payload.diagnosis_error_group_key
        else None
    )

    alert_dispatches_task = None
    if payload.include_alert_dispatches:
        to_ts = scope.to_timestamp or datetime.now(tz=UTC)
        from_ts = scope.from_timestamp or (to_ts - timedelta(days=7))
        alert_dispatches_task = _timed_dashboard_slice(
            "alert_dispatches",
            run_with_session(
                lambda isolated_session: get_dashboard_alert_dispatches(
                    context=context,
                    session=isolated_session,
                    from_timestamp=from_ts,
                    to_timestamp=to_ts,
                    window_minutes=scope.window_minutes,
                    limit=payload.alert_dispatches.limit,
                    offset=payload.alert_dispatches.offset,
                ),
            ),
        )

    optional_tasks = [
        overview_extended_task,
        widgets_task,
        error_groups_task,
        diagnosis_timeline_task,
        diagnosis_failures_task,
        recent_job_failures_task,
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
    recent_job_failures = next(optional_iter) if recent_job_failures_task is not None else None
    diagnosis_error_group_events = (
        next(optional_iter) if diagnosis_error_group_events_task is not None else None
    )
    alert_dispatches = next(optional_iter) if alert_dispatches_task is not None else None
    return DashboardDataQueryResponse(
        overview=overview,
        overview_extended=overview_extended,
        widgets=widgets,
        requests=requests,
        error_groups=error_groups,
        diagnosis_timeline=diagnosis_timeline,
        diagnosis_failures=diagnosis_failures,
        diagnosis_error_group_events=diagnosis_error_group_events,
        recent_job_failures=recent_job_failures,
        alert_dispatches=alert_dispatches,
    )
