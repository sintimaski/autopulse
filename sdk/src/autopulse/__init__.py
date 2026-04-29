"""AutoPulse SDK: FastAPI observability integration."""

from autopulse._monitor import monitor
from autopulse.widgets import (
    BarChartWidget,
    BaseDashboardWidget,
    CardWidget,
    DonutChartWidget,
    HistogramWidget,
    LineChartWidget,
    ScatterPlotWidget,
    StackedAreaWidget,
)


def autopulse(app: object, **kwargs: object) -> None:
    """One-line setup for embedded local AutoPulse mode."""
    options = dict(kwargs)
    options.setdefault("mode", "embedded")
    monitor(app, **options)


__all__ = [
    "monitor",
    "autopulse",
    "BaseDashboardWidget",
    "CardWidget",
    "LineChartWidget",
    "BarChartWidget",
    "DonutChartWidget",
    "HistogramWidget",
    "ScatterPlotWidget",
    "StackedAreaWidget",
]
