from __future__ import annotations

from fastapi import Query

FROM_TIMESTAMP_QUERY = Query(default=None)
TO_TIMESTAMP_QUERY = Query(default=None)
METHOD_QUERY = Query(default=None)
STATUS_CLASS_QUERY = Query(default=None, ge=1, le=5)
PATH_QUERY = Query(default=None)
ENVIRONMENTS_QUERY = Query(default=None)
SERVICES_QUERY = Query(default=None)
LATENCY_MIN_MS_QUERY = Query(default=None, ge=0)
LATENCY_MAX_MS_QUERY = Query(default=None, ge=0)
WINDOW_MINUTES_QUERY = Query(default=60, ge=1, le=7 * 24 * 60)
LIMIT_QUERY = Query(default=50, ge=1, le=200)
OFFSET_QUERY = Query(default=0, ge=0)
EVENT_SQL_FILTER_QUERY = Query(default=None, max_length=1500)
CORRELATION_REQUEST_ID_QUERY = Query(
    default=None,
    max_length=128,
    description="When set, return HTTP events and correlated job rows sharing this request_id.",
)
DEFAULT_WINDOW_MINUTES = 60
