"""Repo-wide pytest hooks (isolated DuckDB path for SDK + backend tests)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Avoid shared default ``.autopulse/events.duckdb`` locks across parallel workers."""
    if os.environ.get("AUTOPULSE_DUCKDB_PATH"):
        return
    root = Path(config.rootpath)
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    duck = root / ".autopulse" / f"pytest-events-{worker}.duckdb"
    duck.parent.mkdir(parents=True, exist_ok=True)
    try:
        from autopulse_backend.services.event_store import shutdown_duckdb_event_store

        shutdown_duckdb_event_store()
    except ModuleNotFoundError:
        pass
    os.environ["AUTOPULSE_DUCKDB_PATH"] = str(duck)
