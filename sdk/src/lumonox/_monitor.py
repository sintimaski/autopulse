"""Backward-compatible re-export shim.

The canonical implementation lives under ``lumonox.fastapi`` and ``lumonox.core``.
This module preserves the legacy import surface that pre-dated the Phase 2
core/adapter split so callers that imported from ``lumonox._monitor`` keep
working without modification. New code (and any test monkeypatching of module-
level helpers) should target the canonical paths directly.
"""

from lumonox.core.config import _MonitorConfig
from lumonox.core.dispatcher import _EventDispatcher, _sdk_version
from lumonox.core.events import (
    _build_infrastructure_widget_payload,
    _split_events_for_ingest_json_budget,
    _stable_error_hash,
)
from lumonox.core.scrubbing import DEFAULT_SCRUB_KEYS, _scrub_value
from lumonox.fastapi.middleware import _add_event_handler, _LumonoxMiddleware, monitor

__all__ = [
    "DEFAULT_SCRUB_KEYS",
    "_EventDispatcher",
    "_LumonoxMiddleware",
    "_MonitorConfig",
    "_add_event_handler",
    "_build_infrastructure_widget_payload",
    "_scrub_value",
    "_sdk_version",
    "_split_events_for_ingest_json_budget",
    "_stable_error_hash",
    "monitor",
]
