from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from lumonox_backend.dashboard.query_snapshot_cache import (
    LiveIngestDelta,
    dashboard_query_snapshot_cache,
)
from lumonox_backend.schemas import DashboardDataQueryRequest, DashboardDataQueryResponse
from lumonox_backend.schemas.dashboard import DashboardDataQueryScope
from lumonox_backend.schemas.dashboard_overview_models import (
    DashboardOverviewBucket,
    DashboardOverviewResponse,
    DashboardReleaseMarker,
    DashboardRequestItem,
    DashboardRequestsResponse,
)


def _supported_query_request() -> DashboardDataQueryRequest:
    return DashboardDataQueryRequest(
        scope=DashboardDataQueryScope(window_minutes=60),
        include_extended=True,
        include_widgets=True,
        include_error_groups=True,
        include_diagnosis=False,
    )


def _base_query_response() -> DashboardDataQueryResponse:
    now = datetime.now(tz=UTC)
    start = now - timedelta(minutes=60)
    return DashboardDataQueryResponse(
        overview=DashboardOverviewResponse(
            server_now=now,
            from_timestamp=start,
            to_timestamp=now,
            request_count=100,
            error_count=10,
            error_rate=0.1,
            avg_latency_ms=50.0,
            requests_per_minute=100 / 60.0,
            series=[
                DashboardOverviewBucket(
                    minute=now.replace(second=0, microsecond=0),
                    request_count=100,
                    error_count=10,
                    avg_latency_ms=50.0,
                    count_2xx=80,
                    count_3xx=0,
                    count_4xx=10,
                    count_5xx=10,
                )
            ],
        ),
        requests=DashboardRequestsResponse(
            server_now=now,
            from_timestamp=start,
            to_timestamp=now,
            total=100,
            limit=25,
            offset=0,
            items=[],
        ),
    )


def test_query_snapshot_cache_serves_seeded_response() -> None:
    project_id = uuid4()
    payload = _supported_query_request()
    response = _base_query_response()
    dashboard_query_snapshot_cache.seed(
        project_id=project_id,
        payload=payload,
        version=3,
        response=response,
    )

    hit = dashboard_query_snapshot_cache.read_if_fresh(
        project_id=project_id,
        payload=payload,
        current_version=3,
    )

    assert hit is not None
    assert hit.overview.request_count == 100
    assert hit.requests.total == 100


def test_query_snapshot_cache_applies_ingest_delta() -> None:
    project_id = uuid4()
    payload = _supported_query_request()
    response = _base_query_response()
    dashboard_query_snapshot_cache.seed(
        project_id=project_id,
        payload=payload,
        version=1,
        response=response,
    )
    now = datetime.now(tz=UTC)
    dashboard_query_snapshot_cache.apply_live_ingest_delta(
        project_id=project_id,
        version=2,
        delta=LiveIngestDelta(
            accepted=2,
            error_count=1,
            latency_total_ms=100.0,
            count_2xx=1,
            count_3xx=0,
            count_4xx=0,
            count_5xx=1,
            requests=(
                DashboardRequestItem(
                    timestamp=now,
                    method="GET",
                    path="/health",
                    status_code=200,
                    latency_ms=12.0,
                    service_name="svc",
                    environment="dev",
                ),
            ),
        ),
    )

    hit = dashboard_query_snapshot_cache.read_if_fresh(
        project_id=project_id,
        payload=payload,
        current_version=2,
    )
    assert hit is not None
    assert hit.overview.request_count >= 102
    assert hit.overview.error_count >= 11
    assert hit.requests.total == hit.overview.request_count
    assert hit.overview.to_timestamp > hit.overview.from_timestamp
    assert len(hit.requests.items) == 1


def test_query_snapshot_cache_delta_trims_release_markers_outside_window() -> None:
    project_id = uuid4()
    payload = _supported_query_request()
    response = _base_query_response()
    start = response.overview.from_timestamp
    response.overview.release_markers = [
        DashboardReleaseMarker(at=start - timedelta(hours=3), release="ancient", git_sha="111"),
        DashboardReleaseMarker(
            at=response.overview.to_timestamp - timedelta(minutes=1),
            release="recent",
            git_sha="222",
        ),
    ]
    dashboard_query_snapshot_cache.seed(
        project_id=project_id,
        payload=payload,
        version=1,
        response=response,
    )
    dashboard_query_snapshot_cache.apply_live_ingest_delta(
        project_id=project_id,
        version=2,
        delta=LiveIngestDelta(
            accepted=1,
            error_count=0,
            latency_total_ms=10.0,
            count_2xx=1,
            count_3xx=0,
            count_4xx=0,
            count_5xx=0,
            requests=(),
        ),
    )

    hit = dashboard_query_snapshot_cache.read_if_fresh(
        project_id=project_id,
        payload=payload,
        current_version=2,
    )
    assert hit is not None
    ws = hit.overview.from_timestamp
    assert all(m.at >= ws for m in hit.overview.release_markers)
    assert not any(m.release == "ancient" for m in hit.overview.release_markers)
    assert any(m.release == "recent" for m in hit.overview.release_markers)


def test_query_snapshot_cache_skips_absolute_scope() -> None:
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    payload = DashboardDataQueryRequest(
        scope=DashboardDataQueryScope(from_timestamp=now - timedelta(minutes=30), to_timestamp=now),
        include_extended=True,
        include_widgets=True,
        include_error_groups=True,
    )
    dashboard_query_snapshot_cache.seed(
        project_id=project_id,
        payload=payload,
        version=1,
        response=_base_query_response(),
    )
    hit = dashboard_query_snapshot_cache.read_if_fresh(
        project_id=project_id,
        payload=payload,
        current_version=1,
    )
    assert hit is None
