from __future__ import annotations

from lumonox.widgets import (
    BarChartWidget,
    CardWidget,
    DonutChartWidget,
    HistogramWidget,
    LineChartWidget,
    ScatterPlotWidget,
    StackedAreaWidget,
)


def test_card_widget_serialization() -> None:
    widget = CardWidget(widget_id="queue_depth", title="Queue depth", value=7, unit="jobs")
    payload = widget.serialize_definition()
    assert payload["type"] == "card"
    assert payload["config"]["unit"] == "jobs"
    assert payload["config"]["page_id"] == "custom"
    assert payload["config"]["section"] == "default"
    points = widget.collect_points()
    assert len(points) == 1
    assert points[0]["value"] == 7.0


def test_chart_widgets_collect_points() -> None:
    line = LineChartWidget(
        widget_id="cpu_line", title="CPU", points=[("2026-01-01T00:00:00Z", 42.5)]
    )
    bar = BarChartWidget(
        widget_id="jobs_by_queue", title="Jobs by queue", bars=[("default", 10), ("slow", 3)]
    )
    donut = DonutChartWidget(
        widget_id="errors_by_type", title="Errors by type", slices=[("timeout", 2)]
    )
    assert line.collect_points()[0]["value"] == 42.5
    assert len(bar.collect_points()) == 2
    assert donut.collect_points()[0]["label"] == "timeout"


def test_extended_widget_types_collect_points() -> None:
    histogram = HistogramWidget(
        widget_id="latency_histogram",
        title="Latency",
        buckets=[("<50ms", 12), ("50-100ms", 8)],
    )
    scatter = ScatterPlotWidget(
        widget_id="route_risk",
        title="Route risk",
        points=[(120.0, 3.5, "/users/{id}")],
        x_label="Volume",
        y_label="Error %",
    )
    stacked = StackedAreaWidget(
        widget_id="outcome_stack",
        title="Outcome stack",
        points=[("2026-01-01T00:00:00Z", "success", 20.0), ("2026-01-01T00:00:00Z", "server", 2.0)],
    )
    assert histogram.serialize_definition()["type"] == "histogram"
    assert len(histogram.collect_points()) == 2
    assert scatter.serialize_definition()["config"]["x_label"] == "Volume"
    assert scatter.collect_points()[0]["label"] == "120.0|/users/{id}"
    assert stacked.serialize_definition()["type"] == "stacked_area"
    assert stacked.collect_points()[1]["label"] == "server"
