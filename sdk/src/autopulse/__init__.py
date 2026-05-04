"""AutoPulse SDK: FastAPI observability integration."""

import os

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
    """One-line FastAPI setup: embedded or remote ingest from env, or ``kwargs``.

    Reads ``AUTOPULSE_MODE`` when ``mode`` is not passed: ``embedded`` (default), ``remote``,
    or ``off`` / ``false`` / ``0`` / ``no`` / ``none`` / ``disabled`` to skip instrumentation.
    Sets ``environment`` to ``development`` when omitted (matches common dashboard filters).
    Honors ``AUTOPULSE_SERVICE_NAME`` when ``service_name`` is not passed.
    """
    options = dict(kwargs)
    if "mode" not in options:
        raw = os.getenv("AUTOPULSE_MODE", "embedded").strip().lower()
        if raw in {"off", "false", "0", "no", "none", "disabled"}:
            return
        options["mode"] = "remote" if raw == "remote" else "embedded"
    if "environment" not in options:
        options["environment"] = "development"
    if "service_name" not in options:
        service_name = os.getenv("AUTOPULSE_SERVICE_NAME", "").strip()
        if service_name:
            options["service_name"] = service_name
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
