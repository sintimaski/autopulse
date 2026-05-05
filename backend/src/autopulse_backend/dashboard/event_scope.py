"""Shared filters so HTTP dashboards ignore background ``job`` rows."""

from __future__ import annotations

from sqlalchemy.sql import ColumnElement

from autopulse_backend.models import Event

HTTP_SCOPED_EVENT_TYPES: tuple[str, ...] = ("request", "error")


def http_scoped_event_types_clause() -> ColumnElement[bool]:
    return Event.type.in_(HTTP_SCOPED_EVENT_TYPES)
