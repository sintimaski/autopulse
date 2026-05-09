from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from lumonox_backend.auth import ProjectContext
from lumonox_backend.dashboard.routes import query_bundle
from lumonox_backend.schemas import (
    DashboardDataQueryRequest,
    DashboardDataQueryResponse,
    DashboardDataQueryScope,
    DashboardDiagnosisErrorGroupEventsResponse,
    DashboardDiagnosisFailureRoutesResponse,
    DashboardDiagnosisTimelineResponse,
    DashboardErrorGroupsResponse,
    DashboardOverviewResponse,
    DashboardRequestsResponse,
)


def _sample_bundle_response() -> DashboardDataQueryResponse:
    now = datetime.now(tz=UTC)
    return DashboardDataQueryResponse(
        overview=DashboardOverviewResponse(
            server_now=now,
            from_timestamp=now - timedelta(minutes=5),
            to_timestamp=now,
            request_count=1,
            error_count=0,
            error_rate=0.0,
            avg_latency_ms=12.0,
            requests_per_minute=0.2,
            series=[],
        ),
        requests=DashboardRequestsResponse(
            server_now=now,
            from_timestamp=now - timedelta(minutes=5),
            to_timestamp=now,
            total=1,
            limit=25,
            offset=0,
            items=[],
        ),
        error_groups=DashboardErrorGroupsResponse(
            server_now=now,
            from_timestamp=now - timedelta(minutes=5),
            to_timestamp=now,
            total=0,
            limit=10,
            offset=0,
            items=[],
        ),
        diagnosis_timeline=DashboardDiagnosisTimelineResponse(
            server_now=now,
            from_timestamp=now - timedelta(minutes=5),
            to_timestamp=now,
            buckets=[],
        ),
        diagnosis_failures=DashboardDiagnosisFailureRoutesResponse(
            server_now=now,
            from_timestamp=now - timedelta(minutes=5),
            to_timestamp=now,
            items=[],
        ),
        diagnosis_error_group_events=DashboardDiagnosisErrorGroupEventsResponse(total=0, items=[]),
    )


def test_select_bundle_tier_prefers_heavy_tiles() -> None:
    payload = DashboardDataQueryRequest(
        scope=DashboardDataQueryScope(window_minutes=60),
        include_extended=True,
    )
    assert query_bundle._select_bundle_tier(payload) == "heavy"


def test_compute_bundle_inflight_dedupe_runs_once(monkeypatch) -> None:
    query_bundle._bundle_inflight.clear()
    call_count = 0
    response = _sample_bundle_response()

    async def fake_run_bundle_query(*, payload, context):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return response

    async def fake_cache_bundle_response(*, cache_key, payload, response):
        return None

    monkeypatch.setattr(query_bundle, "_run_bundle_query", fake_run_bundle_query)
    monkeypatch.setattr(query_bundle, "_cache_bundle_response", fake_cache_bundle_response)

    payload = DashboardDataQueryRequest(scope=DashboardDataQueryScope(window_minutes=60))
    context = ProjectContext(project_id=uuid4())

    async def run_case() -> list[DashboardDataQueryResponse]:
        return await asyncio.gather(
            query_bundle._compute_bundle_with_inflight_dedupe(
                cache_key="same-key",
                payload=payload,
                context=context,
            ),
            query_bundle._compute_bundle_with_inflight_dedupe(
                cache_key="same-key",
                payload=payload,
                context=context,
            ),
        )

    results = asyncio.run(run_case())
    assert call_count == 1
    assert results[0] == response
    assert results[1] == response


def test_mark_project_dashboard_dirty_increments_version() -> None:
    project_id = UUID("00000000-0000-0000-0000-000000000001")

    async def run_case() -> tuple[int, int]:
        query_bundle._bundle_project_versions.clear()
        first = await query_bundle.mark_project_dashboard_dirty(project_id)
        second = await query_bundle.mark_project_dashboard_dirty(project_id)
        return first, second

    first, second = asyncio.run(run_case())
    assert first == 1
    assert second == 2


def test_dashboard_query_request_clamps_pagination_limits() -> None:
    payload = DashboardDataQueryRequest(
        scope=DashboardDataQueryScope(window_minutes=60),
        requests={"limit": 999_999, "offset": -5},
        error_groups={"limit": 9_999, "offset": -1},
    )
    assert payload.requests.limit == 250
    assert payload.requests.offset == 0
    assert payload.error_groups.limit == 100
    assert payload.error_groups.offset == 0


def test_bundle_ttl_prefers_short_heavy_cache(monkeypatch) -> None:
    """Default product tuning: heavy bundles use a shorter cache than light.

    Deployments may override TTLs via env; this test pins defaults for the invariant.
    """
    monkeypatch.setattr(query_bundle, "BUNDLE_LIGHT_CACHE_TTL_SECONDS", 4.0)
    monkeypatch.setattr(query_bundle, "BUNDLE_HEAVY_CACHE_TTL_SECONDS", 1.5)
    light_payload = DashboardDataQueryRequest(scope=DashboardDataQueryScope(window_minutes=60))
    heavy_payload = DashboardDataQueryRequest(
        scope=DashboardDataQueryScope(window_minutes=60),
        include_extended=True,
    )
    assert query_bundle._bundle_ttl_seconds(heavy_payload) < query_bundle._bundle_ttl_seconds(
        light_payload
    )
