"""Shared pytest hooks for SDK tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _reset_duckdb_event_store_after_test() -> Generator[None, None, None]:
    """Reset process-global DuckDB store after each test."""
    yield
    try:
        from lumonox_backend.services.event_store import shutdown_duckdb_event_store
    except ImportError:
        return
    shutdown_duckdb_event_store()
