"""Synthetic studio widgets: one definition per chart type plus layout exercises."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from lumonox_backend.schemas.dashboard_overview_models import (
    DashboardWidgetDefinition,
    DashboardWidgetPoint,
)

LX_STUDIO_PREFIX = "lx_studio_"
_SHOWCASE_PAGE_ID = "lx_showcase"


def _between(resolved_from: datetime, resolved_to: datetime, *, steps: int, i: int) -> datetime:
    if steps <= 1:
        return resolved_to
    delta = resolved_to - resolved_from
    return resolved_from + (delta * i / (steps - 1))


def build_studio_showcase_definitions() -> list[DashboardWidgetDefinition]:
    """Seven widget types on one page with multiple sections and spans."""
    base_page = {
        "page_id": _SHOWCASE_PAGE_ID,
        "page_title": "Widget layout lab",
        "page_description": (
            "Realistic synthetic series for every widget type and common placement patterns."
        ),
        "page_order": 50,
    }
    return [
        DashboardWidgetDefinition(
            widget_id=f"{LX_STUDIO_PREFIX}kpi_card",
            type="card",
            title="Ingest throughput (window)",
            description="Single card in a narrow column (column_span=1).",
            order=10,
            config={
                **base_page,
                "unit": "req/min",
                "section": "kpi_strip",
                "layout_order": 10,
                "column_span": 1,
                "row_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id=f"{LX_STUDIO_PREFIX}split_bar",
            type="bar",
            title="Top routes by volume",
            description="Two-column span beside a donut.",
            order=20,
            config={
                **base_page,
                "unit": "req",
                "section": "split_row",
                "layout_order": 20,
                "column_span": 2,
                "row_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id=f"{LX_STUDIO_PREFIX}split_donut",
            type="donut",
            title="HTTP status families",
            description="Single-column donut next to a wide bar.",
            order=21,
            config={
                **base_page,
                "section": "split_row",
                "layout_order": 21,
                "column_span": 1,
                "row_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id=f"{LX_STUDIO_PREFIX}full_line",
            type="line",
            title="p95 latency trend",
            description="column_span=3 across the grid.",
            order=30,
            config={
                **base_page,
                "color": "#0ea5e9",
                "section": "full_width",
                "layout_order": 30,
                "column_span": 3,
                "row_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id=f"{LX_STUDIO_PREFIX}hist",
            type="histogram",
            title="Request latency distribution",
            description="Full-width histogram buckets.",
            order=40,
            config={
                **base_page,
                "section": "histogram_row",
                "layout_order": 40,
                "column_span": 3,
                "row_span": 1,
            },
        ),
        DashboardWidgetDefinition(
            widget_id=f"{LX_STUDIO_PREFIX}scatter",
            type="scatter",
            title="Error rate vs latency",
            description=(
                "row_span=2 with column_span=2; labels use x|name format "
                "(x is spread for readability)."
            ),
            order=50,
            config={
                **base_page,
                "x_label": "Error pressure (0–100, illustrative)",
                "y_label": "p99 latency (normalized)",
                "section": "scatter_stack",
                "layout_order": 50,
                "column_span": 2,
                "row_span": 2,
            },
        ),
        DashboardWidgetDefinition(
            widget_id=f"{LX_STUDIO_PREFIX}stacked",
            type="stacked_area",
            title="Traffic by environment",
            description="Ten environment series over time (row_span=2, span=1).",
            order=60,
            config={
                **base_page,
                "section": "scatter_stack",
                "layout_order": 60,
                "column_span": 1,
                "row_span": 2,
            },
        ),
    ]


def build_studio_showcase_points(
    resolved_from: datetime,
    resolved_to: datetime,
) -> list[DashboardWidgetPoint]:
    rf = resolved_from.astimezone(UTC)
    rt = resolved_to.astimezone(UTC)
    points: list[DashboardWidgetPoint] = []

    # Card: a few samples so the latest is not arbitrary; trend slightly up
    card_steps = 5
    for i in range(card_steps):
        ts = _between(rf, rt, steps=card_steps, i=i)
        base = 620.0 + float(i) * 18.0 + 6.0 * math.sin(float(i))
        points.append(
            DashboardWidgetPoint(
                widget_id=f"{LX_STUDIO_PREFIX}kpi_card",
                timestamp=ts,
                label=None,
                value=round(base, 1),
            )
        )

    # Line: p95-ish latency (ms) — uneven baseline + deliberate spikes/dips
    line_steps = 24
    for i in range(line_steps):
        ts = _between(rf, rt, steps=line_steps, i=i)
        t = float(i)
        phase = (i / max(line_steps - 1, 1)) * math.pi * 2.0
        base = 48.0 + 14.0 * math.sin(phase * 0.85)
        micro = 9.0 * math.sin(phase * 4.6) + 6.0 * math.sin(phase * 9.1)
        spike = 0.0
        if i % 5 == 2:
            spike += 34.0
        if i % 7 == 4:
            spike += 22.0
        if i % 6 == 0 and i > 0:
            spike -= 12.0
        dip = 18.0 if i in (11, 19) else 0.0
        noise = 5.5 * math.sin(t * 1.7 + 0.4) + 3.0 * math.sin(t * 3.3)
        points.append(
            DashboardWidgetPoint(
                widget_id=f"{LX_STUDIO_PREFIX}full_line",
                timestamp=ts,
                label=None,
                value=max(16.0, round(base + micro + spike - dip + noise, 1)),
            )
        )

    anchor = rt
    route_weights = (
        ("GET /api/v1/orders", 1840.0),
        ("POST /api/v1/checkout", 1210.0),
        ("GET /api/v1/products", 980.0),
        ("POST /ingest", 742.0),
        ("GET /api/v1/users/me", 610.0),
        ("PUT /api/v1/cart", 445.0),
        ("GET /health", 390.0),
        ("GET /api/v1/search", 312.0),
    )
    for label, value in route_weights:
        points.append(
            DashboardWidgetPoint(
                widget_id=f"{LX_STUDIO_PREFIX}split_bar",
                timestamp=anchor,
                label=label,
                value=value,
            )
        )

    # Donut: plausible status mix (counts, not %)
    for label, value in (("2xx", 9420.0), ("3xx", 118.0), ("4xx", 356.0), ("5xx", 94.0)):
        points.append(
            DashboardWidgetPoint(
                widget_id=f"{LX_STUDIO_PREFIX}split_donut",
                timestamp=anchor,
                label=label,
                value=value,
            )
        )

    # Histogram: bell-ish latency buckets (counts)
    hist = (
        ("0–25ms", 180.0),
        ("25–75ms", 520.0),
        ("75–150ms", 890.0),
        ("150–300ms", 410.0),
        ("300–800ms", 120.0),
        (">800ms", 38.0),
    )
    for label, value in hist:
        points.append(
            DashboardWidgetPoint(
                widget_id=f"{LX_STUDIO_PREFIX}hist",
                timestamp=anchor,
                label=label,
                value=value,
            )
        )

    # Scatter: x uses a wide 0–100 spread so points are not clumped at the left of the axis
    scatter_specs = (
        ("8|api-gateway", 6.2),
        ("22|checkout-svc", 9.4),
        ("36|search-index", 11.8),
        ("48|payments-core", 14.5),
        ("58|legacy-auth", 18.6),
        ("68|reporting-job", 22.1),
        ("78|notifications", 7.9),
        ("92|inventory", 16.2),
    )
    for label, y in scatter_specs:
        points.append(
            DashboardWidgetPoint(
                widget_id=f"{LX_STUDIO_PREFIX}scatter",
                timestamp=anchor,
                label=label,
                value=y,
            )
        )

    # Stacked area: ten environments × several timestamps — comparable bands
    # so the stack reads as multi-slice.
    ts_keys = [_between(rf, rt, steps=8, i=i) for i in range(8)]
    series_profiles = (
        ("production", (14.0, 2.8, 1.0)),
        ("staging", (12.0, 2.5, 0.95)),
        ("development", (11.0, 2.2, 0.9)),
        ("qa", (10.5, 2.0, 0.85)),
        ("sandbox", (10.0, 1.9, 0.8)),
        ("canary", (9.5, 2.6, 1.05)),
        ("eu-west", (9.0, 1.7, 0.75)),
        ("us-east", (8.8, 1.8, 0.78)),
        ("us-west", (8.5, 1.75, 0.76)),
        ("preview", (8.2, 1.65, 0.72)),
    )
    for env_index, (series_name, (base_amp, diurnal, jitter)) in enumerate(series_profiles):
        for ti, ts in enumerate(ts_keys):
            hourish = math.sin((ti / 7.0) * math.pi * 2.0)
            env_phase = float(env_index) * 0.55
            v = (
                base_amp
                + diurnal * 10.0 * hourish
                + jitter * float(ti) * 2.8
                + 4.5 * math.sin(float(ti) * 1.3 + env_phase)
                + 3.0 * math.sin(env_phase + float(ti) * 0.7)
            )
            points.append(
                DashboardWidgetPoint(
                    widget_id=f"{LX_STUDIO_PREFIX}stacked",
                    timestamp=ts,
                    label=series_name,
                    value=max(2.0, round(v, 1)),
                )
            )

    return points


def strip_studio_showcase_rows(
    definitions: list[DashboardWidgetDefinition],
    points: list[DashboardWidgetPoint],
) -> tuple[list[DashboardWidgetDefinition], list[DashboardWidgetPoint]]:
    return (
        [d for d in definitions if not d.widget_id.startswith(LX_STUDIO_PREFIX)],
        [p for p in points if not p.widget_id.startswith(LX_STUDIO_PREFIX)],
    )


def merge_studio_showcase_widgets(
    definitions: list[DashboardWidgetDefinition],
    points: list[DashboardWidgetPoint],
    resolved_from: datetime,
    resolved_to: datetime,
    *,
    demo_enabled: bool,
) -> tuple[list[DashboardWidgetDefinition], list[DashboardWidgetPoint]]:
    """Strip any stale showcase rows; only re-inject synthetic rows in demo mode.

    The bundled ``lx_showcase`` page is fabricated data — gated behind
    ``LUMONOX_STUDIO_SHOWCASE_DEMO`` so production projects never see fake routes
    or metrics. The strip always runs so a flag flip leaves no orphaned rows.
    """
    defs, pts = strip_studio_showcase_rows(definitions, points)
    if not demo_enabled:
        return defs, pts
    extra_defs = build_studio_showcase_definitions()
    extra_pts = build_studio_showcase_points(resolved_from, resolved_to)
    return defs + extra_defs, pts + extra_pts
