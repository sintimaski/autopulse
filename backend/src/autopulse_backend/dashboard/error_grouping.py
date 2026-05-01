from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, exists, literal, or_, select
from sqlalchemy.orm import aliased

from autopulse_backend.dashboard.payload_limits import (
    MAX_ERROR_GROUP_MESSAGE_CHARS,
    MAX_ERROR_GROUP_STACK_CHARS,
)
from autopulse_backend.models import Event

DASHBOARD_GROUP_HASH_PATH_SEP = "\x1e"


def synthetic_error_key(
    exception_type: str | None,
    exception_message: str | None,
    path: str,
) -> str:
    digest = hashlib.sha256()
    digest.update((exception_type or "").encode("utf-8"))
    digest.update(b"|")
    digest.update((exception_message or "").encode("utf-8"))
    digest.update(b"|")
    digest.update(path.encode("utf-8"))
    return digest.hexdigest()


def derived_error_group_key(payload_dict: dict, path: str) -> str:
    raw_hash = payload_dict.get("error_hash")
    error_hash = raw_hash.strip() if isinstance(raw_hash, str) else ""
    route = path or ""
    et_raw = payload_dict.get("exception_type")
    exception_type = et_raw if isinstance(et_raw, str) else None
    exception_message = (
        payload_dict.get("exception_message")
        if isinstance(payload_dict.get("exception_message"), str)
        else None
    )
    if error_hash:
        return f"{error_hash}{DASHBOARD_GROUP_HASH_PATH_SEP}{route}"
    return synthetic_error_key(exception_type, exception_message, route)


def error_like_events_predicate(resolved_from: datetime, resolved_to: datetime):
    """Match SDK `type=error` rows, plus `type=request` 5xx when no paired error (same request_id).

    HTTPException / synthetic apps often emit only a request row for 503/500; uncaught handlers emit
    both request+error with the same request_id — exclude the request half from grouping.
    """
    paired_error = aliased(Event)
    return or_(
        Event.type == "error",
        and_(
            Event.type == "request",
            Event.status_code >= 500,
            or_(
                Event.request_id.is_(None),
                ~exists(
                    select(literal(1)).where(
                        paired_error.project_id == Event.project_id,
                        paired_error.type == "error",
                        paired_error.request_id == Event.request_id,
                        paired_error.request_id.isnot(None),
                        Event.request_id.isnot(None),
                        paired_error.timestamp >= resolved_from,
                        paired_error.timestamp <= resolved_to,
                    )
                ),
            ),
        ),
    )


def error_group_labels(
    path: str,
    status_code: int,
    exception_type: str | None,
    exception_message: str | None,
    sample_stack_trace: str | None,
) -> tuple[str, str, str | None]:
    """Fill exception/message when ingest omitted SDK fields (e.g. type=error with only status)."""
    exc: str | None = (
        exception_type.strip()
        if isinstance(exception_type, str) and exception_type.strip()
        else None
    )
    msg: str | None = (
        exception_message.strip()
        if isinstance(exception_message, str) and exception_message.strip()
        else None
    )
    stack: str | None = (
        sample_stack_trace.strip()
        if isinstance(sample_stack_trace, str) and sample_stack_trace.strip()
        else None
    )
    if exc is None:
        exc = f"HTTP {status_code}" if status_code else "Error"
    if msg is None:
        msg = (
            f"Request to {path} failed with HTTP {status_code} (no exception payload on ingest)."
            if status_code
            else "No exception metadata was sent with this error event."
        )
    if len(msg) > MAX_ERROR_GROUP_MESSAGE_CHARS:
        msg = f"{msg[: MAX_ERROR_GROUP_MESSAGE_CHARS - 1]}…"
    if stack is not None and len(stack) > MAX_ERROR_GROUP_STACK_CHARS:
        stack = f"{stack[: MAX_ERROR_GROUP_STACK_CHARS - 1]}…"
    return exc, msg, stack


@dataclass(slots=True)
class SQLiteErrorGroup:
    group_key: str
    count: int
    first_seen: datetime
    last_seen: datetime
    path: str
    exception_type: str | None
    message: str | None
    sample_stack_trace: str | None
    sample_id: int
    sample_status_code: int
