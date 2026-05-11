from __future__ import annotations

from enum import StrEnum

from fastapi import Query


class DashboardRequestsFocus(StrEnum):
    """Optional query presets for ``/dashboard/requests``."""

    errors = "errors"


FROM_TIMESTAMP_QUERY = Query(default=None)
TO_TIMESTAMP_QUERY = Query(default=None)
METHOD_QUERY = Query(default=None)
STATUS_CLASS_QUERY = Query(default=None, ge=1, le=5)
REQUESTS_FOCUS_QUERY = Query(
    default=None,
    description=(
        "Diagnosis preset for the requests table. "
        "`errors` applies HTTP 5xx filtering (same as status_class=5) when status_class is unset."
    ),
)
PATH_QUERY = Query(default=None)
ENVIRONMENTS_QUERY = Query(default=None)
SERVICES_QUERY = Query(default=None)
LATENCY_MIN_MS_QUERY = Query(default=None, ge=0)
LATENCY_MAX_MS_QUERY = Query(default=None, ge=0)
WINDOW_MINUTES_QUERY = Query(default=60, ge=1, le=7 * 24 * 60)
LIMIT_QUERY = Query(default=50, ge=1, le=200)
OFFSET_QUERY = Query(default=0, ge=0)
EVENT_SQL_FILTER_QUERY = Query(default=None, max_length=1500)
DEFAULT_WINDOW_MINUTES = 60
