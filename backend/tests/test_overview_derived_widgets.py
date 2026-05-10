from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lumonox_backend.dashboard.overview_derived_widgets import (
    build_overview_derived_widgets,
    merge_overview_derived_widgets,
)
from lumonox_backend.schemas.dashboard_overview_models import (
    DashboardOverviewBucket,
    DashboardOverviewResponse,
    DashboardWidgetDefinition,
    DashboardWidgetPoint,
    DashboardWidgetsResponse,
)


def _overview_with_series() -> DashboardOverviewResponse:
    now = datetime.now(tz=UTC)
    start = now - timedelta(minutes=5)
    m0 = start.replace(second=0, microsecond=0)
    m1 = (start + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return DashboardOverviewResponse(
        server_now=now,
        from_timestamp=start,
        to_timestamp=now,
        request_count=30,
        error_count=3,
        error_rate=0.1,
        avg_latency_ms=42.5,
        requests_per_minute=6.0,
        series=[
            DashboardOverviewBucket(
                minute=m0,
                request_count=10,
                error_count=1,
                avg_latency_ms=40.0,
                count_2xx=8,
                count_3xx=0,
                count_4xx=1,
                count_5xx=1,
            ),
            DashboardOverviewBucket(
                minute=m1,
                request_count=20,
                error_count=2,
                avg_latency_ms=44.0,
                count_2xx=18,
                count_3xx=0,
                count_4xx=1,
                count_5xx=1,
            ),
        ],
    )


def test_build_overview_derived_widgets_status_totals_and_peak_bar() -> None:
    overview = _overview_with_series()
    defs, pts = build_overview_derived_widgets(overview)
    assert {d.widget_id for d in defs} == {
        "lx_home_status_donut",
        "lx_home_peak_minutes_bar",
        "lx_home_window_requests",
        "lx_home_window_avg_latency",
    }
    donut = [p for p in pts if p.widget_id == "lx_home_status_donut"]
    by_label = {p.label: p.value for p in donut}
    assert by_label["2xx"] == 26.0
    assert by_label["4xx"] == 2.0
    assert by_label["5xx"] == 2.0
    bars = [p for p in pts if p.widget_id == "lx_home_peak_minutes_bar"]
    assert len(bars) >= 1
    assert max(p.value for p in bars) == 20.0


def test_merge_overview_derived_widgets_replaces_lx_home_prefix() -> None:
    overview = _overview_with_series()
    now = overview.to_timestamp
    base = DashboardWidgetsResponse(
        server_now=now,
        from_timestamp=overview.from_timestamp,
        to_timestamp=overview.to_timestamp,
        definitions=[
            DashboardWidgetDefinition(
                widget_id="lx_home_window_requests",
                type="card",
                title="stale",
                description=None,
                order=1,
                config={},
            ),
            DashboardWidgetDefinition(
                widget_id="user_custom",
                type="card",
                title="Keep",
                description=None,
                order=2,
                config={},
            ),
        ],
        points=[
            DashboardWidgetPoint(
                widget_id="lx_home_window_requests",
                timestamp=now,
                label=None,
                value=1.0,
            ),
            DashboardWidgetPoint(
                widget_id="user_custom",
                timestamp=now,
                label=None,
                value=99.0,
            ),
        ],
    )
    merged = merge_overview_derived_widgets(base, overview)
    ids = {d.widget_id for d in merged.definitions}
    assert "user_custom" in ids
    assert merged.definitions[-1].widget_id == "lx_home_window_avg_latency"
    custom_pts = [p for p in merged.points if p.widget_id == "user_custom"]
    assert len(custom_pts) == 1
    assert custom_pts[0].value == 99.0
    req_pts = [p for p in merged.points if p.widget_id == "lx_home_window_requests"]
    assert len(req_pts) == 1
    assert req_pts[0].value == 30.0
