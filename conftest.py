"""Repo-wide pytest hooks (isolated DuckDB path for SDK + backend tests)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Avoid shared default ``.lumonox/events.duckdb`` locks across parallel workers."""
    if os.environ.get("LUMONOX_DUCKDB_PATH"):
        return
    root = Path(config.rootpath)
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    duck = root / ".lumonox" / f"pytest-events-{worker}.duckdb"
    duck.parent.mkdir(parents=True, exist_ok=True)
    try:
        from lumonox_backend.services.event_store import shutdown_duckdb_event_store

        shutdown_duckdb_event_store()
    except ModuleNotFoundError:
        pass
    os.environ["LUMONOX_DUCKDB_PATH"] = str(duck)
