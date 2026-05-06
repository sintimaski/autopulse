"""Compatibility shim: settings live in `autopulse_backend.core.config`."""

from __future__ import annotations

from autopulse_backend.core.config import (
    Settings,
    get_settings,
    normalize_event_plane_shards_path,
    normalize_event_plane_snapshots_path,
    normalize_event_store_duckdb_path,
    resolve_autopulse_data_root,
)

__all__ = [
    "Settings",
    "get_settings",
    "normalize_event_plane_shards_path",
    "normalize_event_plane_snapshots_path",
    "normalize_event_store_duckdb_path",
    "resolve_autopulse_data_root",
]
