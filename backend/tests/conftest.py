from __future__ import annotations

import os
import tempfile
import warnings
from contextlib import suppress
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

# Before importing lumonox (which may load ``backend/.env``), pin defaults when the
# integration suite uses the implicit per-session SQLite URL. Otherwise a developer
# ``backend/.env`` that sets ``LUMONOX_EVENT_STORE=duckdb`` makes ingest tests query an
# empty SQL ``events`` table, and background schedulers race parquet/DuckDB during
# ``TestClient`` runs.
_backend_test_db_env = (os.getenv("BACKEND_TEST_DATABASE_URL") or "").strip()
_backend_test_db_is_isolated_sqlite_memory = (
    _backend_test_db_env.lower().startswith("sqlite") and ":memory:" in _backend_test_db_env.lower()
)
_using_default_backend_integration_db = (
    not _backend_test_db_env or _backend_test_db_is_isolated_sqlite_memory
)
if _using_default_backend_integration_db:
    os.environ["LUMONOX_EVENT_STORE"] = "sqlite"
    os.environ["LUMONOX_EVENT_PLANE_MODE"] = "duckdb_single_writer"
    os.environ["JOBS_ENABLE_SCHEDULER"] = "false"
    # Local ``backend/.env`` often enables origin checks; TestClient posts omit ``Origin``.
    os.environ["DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS"] = "false"
    # Integration tests use ingest API keys on dashboard read routes (no magic-link session).
    os.environ["DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK"] = "true"
    # Age-based retention tests expect time-window deletes; size-only mode skips them.
    os.environ["LUMONOX_SQLITE_SIZE_RETENTION_ONLY"] = "false"
    # Inline SQL aggregates + widget writes keep read-your-writes tests deterministic without
    # relying on the aggregate worker loop (scheduler is off in this profile).
    os.environ["INGEST_ASYNC_AGGREGATE_ENABLED"] = "false"
    _pytest_duck_root = Path(tempfile.mkdtemp(prefix="lumonox-pytest-duckdb-"))
    os.environ["LUMONOX_DUCKDB_PATH"] = str(_pytest_duck_root / "events.duckdb")

# Postgres + Starlette TestClient/asyncio.run mix: avoid asyncpg connections bound to a
# finished event loop (see ``database.session._async_pool_kwargs``).
if (os.getenv("BACKEND_TEST_DATABASE_URL") or "").strip().lower().startswith("postgresql"):
    os.environ.setdefault("LUMONOX_TEST_PG_ASYNC_NULLPOOL", "true")

from sqlalchemy.engine.url import make_url  # noqa: E402


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


def _sqlite_url_uses_isolated_memory(database_url: str) -> bool:
    """True when each new connection would get a fresh empty DB (breaks Alembic + tests)."""
    normalized = database_url.replace("+aiosqlite", "").replace("+pysqlite", "").strip().lower()
    if not normalized.startswith("sqlite"):
        return False
    if ":memory:" in normalized:
        return True
    url = make_url(normalized)
    return (url.database or "") in {":memory:", ""}


def _assert_sqlite_projects_table_present(database_url: str) -> None:
    """Catch misconfigured in-memory URLs where migrations and tests use different DBs."""
    if not database_url.lower().startswith("sqlite"):
        return
    if _sqlite_url_uses_isolated_memory(database_url):
        return
    sync = database_url.replace("+aiosqlite", "").replace("+pysqlite", "")
    engine = create_engine(sync)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='projects' LIMIT 1")
            ).first()
    finally:
        engine.dispose()
    if row is None:
        raise RuntimeError(
            "After Alembic upgrade, SQLite is missing the `projects` table. "
            "If BACKEND_TEST_DATABASE_URL uses in-memory SQLite (`:memory:`), switch to a "
            "file-backed URL (see backend/tests/conftest.py) — each engine connection would "
            "otherwise see an empty database."
        )


@pytest.fixture(scope="session")
def backend_test_database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Integration test database URL.

    Precedence:
    - ``BACKEND_TEST_DATABASE_URL`` when set (CI often uses Postgres here).
    - Otherwise a **session-scoped** SQLite file under pytest's basetemp so local
      ``uv run pytest`` runs DB-backed tests without touching ``DATABASE_URL`` from
      a developer ``.env`` or the default repo-relative DB path.

    Returns the **canonical** URL from :func:`get_settings().database_url` after pinning
    ``DATABASE_URL`` (SQLite paths are rewritten by ``normalize_database_url``). Alembic
    and tests must use the same string or migrations land on a different file than the
    assertion and async engines open.
    """
    configured = (os.getenv("BACKEND_TEST_DATABASE_URL") or "").strip()
    if configured and _sqlite_url_uses_isolated_memory(configured):
        warnings.warn(
            "BACKEND_TEST_DATABASE_URL points at in-memory SQLite; that breaks this suite "
            "(Alembic and tests open separate connections). Using a session-scoped temp file "
            "instead. Unset BACKEND_TEST_DATABASE_URL or use a file path.",
            stacklevel=2,
        )
        configured = ""
    if configured:
        candidate = configured
    else:
        db_path = tmp_path_factory.mktemp("lumonox_backend_integration") / "integration.sqlite3"
        # ``sqlite+aiosqlite:///{absolute_path}`` → four slashes after the scheme so
        # ``normalize_database_url`` keeps a true filesystem path (see ``core.config``).
        candidate = f"sqlite+aiosqlite:///{db_path.resolve()}"

    os.environ["DATABASE_URL"] = candidate
    os.environ.setdefault("INGEST_REQUIRE_HTTPS", "false")
    os.environ.setdefault("INTERNAL_METRICS_BEARER_TOKEN", "test-internal-metrics-token")

    from lumonox_backend.core.config import get_settings  # noqa: PLC0415
    from lumonox_backend.database import upgrade_to_head  # noqa: PLC0415

    effective = get_settings().database_url
    if effective != candidate:
        os.environ["DATABASE_URL"] = effective

    try:
        upgrade_to_head()
    except Exception as exc:
        if not _maybe_reset_stale_sqlite_migrations(effective, exc):
            raise
        upgrade_to_head()

    _assert_sqlite_projects_table_present(effective)
    return effective


@pytest.fixture(scope="session", autouse=True)
def _ensure_session_backend_database_migrated(backend_test_database_url: str) -> None:
    """Ensure session DB migration runs once (dependency on ``backend_test_database_url``)."""
    _ = backend_test_database_url
