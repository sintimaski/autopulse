"""Lumonox SDK: FastAPI observability integration."""

import os

from lumonox._jobs import capture_background_job
from lumonox._monitor import monitor
from lumonox.widgets import (
    BarChartWidget,
    BaseDashboardWidget,
    CardWidget,
    DonutChartWidget,
    HistogramWidget,
    LineChartWidget,
    ScatterPlotWidget,
    StackedAreaWidget,
)


def lumonox(app: object, **kwargs: object) -> None:
    """One-line FastAPI setup: remote ingest from env, or ``kwargs``.

    Reads ``LUMONOX_MODE`` when ``mode`` is not passed: ``remote`` (default), or
    ``off`` / ``false`` / ``0`` / ``no`` / ``none`` / ``disabled`` to skip instrumentation.
    ``embedded`` is treated as ``remote`` (embedded mode was removed).
    Sets ``environment`` to ``development`` when omitted (matches common dashboard filters).
    Honors ``LUMONOX_SERVICE_NAME`` when ``service_name`` is not passed.
    """
    options = dict(kwargs)
    if "mode" not in options:
        raw = os.getenv("LUMONOX_MODE", "remote").strip().lower()
        if raw in {"off", "false", "0", "no", "none", "disabled"}:
            return
        options["mode"] = "remote"
    if "environment" not in options:
        options["environment"] = "development"
    if "service_name" not in options:
        service_name = os.getenv("LUMONOX_SERVICE_NAME", "").strip()
        if service_name:
            options["service_name"] = service_name
    monitor(app, **options)


__all__ = [
    "monitor",
    "lumonox",
    "capture_background_job",
    "BaseDashboardWidget",
    "CardWidget",
    "LineChartWidget",
    "BarChartWidget",
    "DonutChartWidget",
    "HistogramWidget",
    "ScatterPlotWidget",
    "StackedAreaWidget",
]
