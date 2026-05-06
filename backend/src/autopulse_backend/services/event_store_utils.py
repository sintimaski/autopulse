from __future__ import annotations

from datetime import UTC, datetime
from os import getenv
from typing import Any


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def as_duckdb_timestamp(value: datetime) -> str:
    return as_utc(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def duckdb_connect_config() -> dict[str, Any]:
    """Per-connection DuckDB settings (see DuckDB configuration / pragmas docs)."""
    cfg: dict[str, Any] = {}
    raw_threads = getenv("AUTOPULSE_DUCKDB_THREADS")
    if raw_threads and raw_threads.strip():
        try:
            threads = max(1, min(int(raw_threads.strip()), 128))
            cfg["threads"] = str(threads)
        except ValueError:
            pass
    raw_mem = getenv("AUTOPULSE_DUCKDB_MEMORY_LIMIT")
    if raw_mem and raw_mem.strip():
        cfg["memory_limit"] = raw_mem.strip()
    return cfg
