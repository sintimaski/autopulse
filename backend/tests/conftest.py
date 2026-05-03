from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path

import pytest
from sqlalchemy.engine.url import make_url

from autopulse_backend.database import upgrade_to_head


def _sqlite_file_paths(database_url: str) -> list[Path] | None:
    """Return on-disk SQLite paths (including WAL sidecars) or None if not file-backed."""
    normalized = database_url.replace("+aiosqlite", "").replace("+pysqlite", "")
    if not normalized.startswith("sqlite"):
        return None
    url = make_url(normalized)
    db_path = url.database
    if db_path is None or db_path in {":memory:", ""}:
        return None
    path = Path(db_path)
    path = (Path.cwd() / path).resolve() if not path.is_absolute() else path.resolve()
    return [path, Path(f"{path}-wal"), Path(f"{path}-shm")]


def _unlink_sqlite_files(paths: list[Path]) -> None:
    for p in paths:
        with suppress(OSError):
            p.unlink(missing_ok=True)


def _maybe_reset_stale_sqlite_migrations(database_url: str, exc: BaseException) -> bool:
    """Stale alembic_version rows on a leftover file DB cause 'can't locate revision'."""
    if "locate revision" not in str(exc).lower():
        return False
    paths = _sqlite_file_paths(database_url)
    if not paths:
        return False
    _unlink_sqlite_files(paths)
    return True


@pytest.fixture(scope="session")
def backend_test_database_url() -> str:
    """Explicit test DB only — do not fall back to ``DATABASE_URL`` (dev .env / app defaults)."""
    value = os.getenv("BACKEND_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set BACKEND_TEST_DATABASE_URL to run backend integration tests.")
    return value


@pytest.fixture(scope="session", autouse=True)
def configure_backend_database() -> None:
    """Run migrations when ``BACKEND_TEST_DATABASE_URL`` is set; ignore ``DATABASE_URL`` alone."""
    value = os.getenv("BACKEND_TEST_DATABASE_URL")
    if not value:
        return
    os.environ["DATABASE_URL"] = value
    os.environ.setdefault("INGEST_REQUIRE_HTTPS", "false")
    os.environ.setdefault("INTERNAL_METRICS_BEARER_TOKEN", "test-internal-metrics-token")
    try:
        upgrade_to_head()
    except Exception as exc:
        if not _maybe_reset_stale_sqlite_migrations(value, exc):
            raise
        upgrade_to_head()
