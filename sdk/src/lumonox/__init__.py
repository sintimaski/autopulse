"""Lumonox SDK: FastAPI observability integration."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from lumonox.core.jobs import capture_background_job
from lumonox.fastapi.middleware import monitor
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


if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI

    create_app: Callable[..., FastAPI]
    mount_on_app: Callable[..., FastAPI]


def __getattr__(name: str) -> Any:
    """Lazy backend API (``lumonox`` PyPI) so ``lumonox-sdk`` stays light when used alone."""
    if name == "create_app":
        from lumonox_backend.app import create_app as _create_app

        return _create_app
    if name == "mount_on_app":
        from lumonox_backend.app import mount_on_app as _mount_on_app

        return _mount_on_app
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


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
    "create_app",
    "mount_on_app",
]
