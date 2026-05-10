"""Overview-window synthetic dashboard widgets (server-computed, not persisted).

Merged into ``POST /dashboard/query`` widget slices so the home dashboard can show
pie/bar + KPI cards aligned with the same overview window as traffic cards.
"""

from __future__ import annotations

from lumonox_backend.dashboard.widget_layout import build_widget_layout
from lumonox_backend.schemas.dashboard_overview_models import (
    DashboardOverviewBucket,
    DashboardOverviewResponse,
    DashboardWidgetDefinition,
    DashboardWidgetPoint,
    DashboardWidgetsResponse,
)

LX_HOME_WIDGET_ID_PREFIX = "lx_home_"


def _sum_series_status_counts(series: list[DashboardOverviewBucket]) -> tuple[int, int, int, int]:
    t2 = t3 = t4 = t5 = 0
    for bucket in series:
        t2 += int(bucket.count_2xx)
        t3 += int(bucket.count_3xx)
        t4 += int(bucket.count_4xx)
        t5 += int(bucket.count_5xx)
    return t2, t3, t4, t5


def build_overview_derived_widgets(
    overview: DashboardOverviewResponse,
) -> tuple[list[DashboardWidgetDefinition], list[DashboardWidgetPoint]]:
    """Return four widget definitions (donut, bar, two cards) plus their points."""
    anchor = overview.to_timestamp
    definitions: list[DashboardWidgetDefinition] = [
        DashboardWidgetDefinition(
            widget_id="lx_home_status_donut",
            type="donut",
            title="Responses by status class",
            description="Share of HTTP status families in the overview window",
            order=901,
            config={
                "page_id": "overview",
                "page_title": "Overview widgets",
                "section": "charts",
                "column_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id="lx_home_peak_minutes_bar",
            type="bar",
            title="Busiest time buckets",
            description="Top buckets by request volume in the overview series",
            order=902,
            config={
                "unit": "req",
                "page_id": "overview",
                "page_title": "Overview widgets",
                "section": "charts",
                "column_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id="lx_home_window_requests",
            type="card",
            title="Requests in window",
            description="Total successful ingest requests counted in overview",
            order=903,
            config={
                "unit": "requests",
                "page_id": "overview",
                "page_title": "Overview widgets",
                "section": "kpis",
                "column_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id="lx_home_window_avg_latency",
            type="card",
            title="Avg latency (window)",
            description="Request-weighted mean latency for the overview window",
            order=904,
            config={
                "unit": "ms",
                "page_id": "overview",
                "page_title": "Overview widgets",
                "section": "kpis",
                "column_span": 1,
            },
        ),
    ]

    points: list[DashboardWidgetPoint] = []
    t2, t3, t4, t5 = _sum_series_status_counts(overview.series)
    for label, count in (("2xx", t2), ("3xx", t3), ("4xx", t4), ("5xx", t5)):
        points.append(
            DashboardWidgetPoint(
                widget_id="lx_home_status_donut",
                timestamp=anchor,
                label=label,
                value=float(count),
            )
        )

    ranked = sorted(
        (b for b in overview.series if int(b.request_count) > 0),
        key=lambda b: int(b.request_count),
        reverse=True,
    )[:6]
    for bucket in ranked:
        label = bucket.minute.strftime("%m/%d %H:%M")
        points.append(
            DashboardWidgetPoint(
                widget_id="lx_home_peak_minutes_bar",
                timestamp=anchor,
                label=label,
                value=float(bucket.request_count),
            )
        )
    if not ranked:
        points.append(
            DashboardWidgetPoint(
                widget_id="lx_home_peak_minutes_bar",
                timestamp=anchor,
                label="No traffic",
                value=0.0,
            )
        )

    points.append(
        DashboardWidgetPoint(
            widget_id="lx_home_window_requests",
            timestamp=anchor,
            label=None,
            value=float(overview.request_count),
        )
    )
    points.append(
        DashboardWidgetPoint(
            widget_id="lx_home_window_avg_latency",
            timestamp=anchor,
            label=None,
            value=float(overview.avg_latency_ms),
        )
    )
    return definitions, points


def merge_overview_derived_widgets(
    widgets: DashboardWidgetsResponse,
    overview: DashboardOverviewResponse,
) -> DashboardWidgetsResponse:
    """Strip any prior ``lx_home_*`` rows and append freshly derived overview widgets."""
    defs = [d for d in widgets.definitions if not d.widget_id.startswith(LX_HOME_WIDGET_ID_PREFIX)]
    pts = [p for p in widgets.points if not p.widget_id.startswith(LX_HOME_WIDGET_ID_PREFIX)]
    extra_defs, extra_pts = build_overview_derived_widgets(overview)
    return widgets.model_copy(
        update={
            "definitions": defs + extra_defs,
            "points": pts + extra_pts,
            "layout": build_widget_layout(defs + extra_defs),
        }
    )
