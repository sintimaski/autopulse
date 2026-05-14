from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from os import getenv
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.asyncio import (
    async_sessionmaker as async_sessionmaker_type,
)
from sqlalchemy.pool import NullPool

from lumonox_backend.core.config import get_settings

# Read/default engines, plus a parallel set of "write" engines — see the comment below.
_engines: dict[str, AsyncEngine] = {}
_session_makers: dict[str, async_sessionmaker_type[AsyncSession]] = {}
_write_engines: dict[str, AsyncEngine] = {}
_write_session_makers: dict[str, async_sessionmaker_type[AsyncSession]] = {}

# A single Lumonox process drives several concurrent writers against the metadata
# DB — the ingest hot path, the async aggregate worker, the SQL-tail repair job —
# alongside the dashboard's reads. File-backed SQLite allows exactly one writer at
# a time, so surviving that needs WAL (readers never block the writer), a busy
# timeout (a writer that finds the DB locked waits instead of erroring), and one
# more thing the first two miss on their own:
#
# SQLAlchemy/SQLite open a *deferred* transaction. A transaction that does a SELECT
# and then a write must upgrade SHARED -> RESERVED mid-transaction, and SQLite
# refuses to run the busy handler on that upgrade — it could deadlock — so the
# write fails *immediately* with "database is locked" no matter how high the busy
# timeout is. Under load that snowballed: failed writes queued repair items and
# worker retries, which added more concurrent writers, until even the
# ``POST /ingest`` idempotency-key insert was losing the race.
#
# Fix: a second set of engines for write transactions (``get_write_engine`` /
# ``write_session`` / ``get_write_session_maker``) that open every transaction with
# ``BEGIN IMMEDIATE`` — the write lock is taken at statement one, so a read-then-
# write transaction never has to upgrade and concurrent writers cleanly wait-and-
# retry under the busy timeout. Read transactions keep the default deferred
# ``BEGIN``, so they stay fully concurrent under WAL and never hold the write lock.
# Code paths that write must use ``write_session()`` / ``get_write_session_maker``;
# read-only callers stay on ``get_db_session`` / ``get_session_maker``.
#
# ``BEGIN IMMEDIATE`` is not free — it serializes writers — so a write transaction
# must stay short and must not be held open across slow non-SQLite work (a DuckDB
# write, network I/O); keep ``write_session()`` scopes tight.
#
# Postgres has real MVCC, so ``get_write_engine`` just returns the standard engine
# there. Retention ``VACUUM`` is also unaffected — it runs on its own raw
# ``sqlite3`` connection (see ``maintenance/retention_sqlite.py``).
_SQLITE_BUSY_TIMEOUT_MS = 30_000


def _configure_sqlite_connection(dbapi_connection: Any, _record: Any) -> None:
    """Apply WAL + busy-timeout pragmas to every new SQLite connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def _configure_sqlite_write_connection(dbapi_connection: Any, _record: Any) -> None:
    """WAL + busy-timeout pragmas, and hand transaction control to SQLAlchemy.

    ``isolation_level = None`` disables the DBAPI driver's implicit ``BEGIN`` so the
    ``begin`` event (``_begin_immediate``) can emit ``BEGIN IMMEDIATE`` instead. It
    is set first so the PRAGMAs still run in autocommit — ``journal_mode=WAL``
    cannot be set inside a transaction.
    """
    dbapi_connection.isolation_level = None
    _configure_sqlite_connection(dbapi_connection, _record)


def _begin_immediate(connection: Any) -> None:
    """Open write-engine transactions with ``BEGIN IMMEDIATE`` (write lock up front).

    Concurrent writers then cleanly wait-and-retry under ``busy_timeout`` instead of
    failing on a SHARED -> RESERVED upgrade. See the module comment for the rationale.
    """
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def _async_pool_kwargs(database_url: str) -> dict[str, Any]:
    """Connection pool options: NullPool for SQLite; bounded pool for Postgres/async drivers."""
    if database_url.startswith("sqlite"):
        return {
            "pool_pre_ping": True,
            "poolclass": NullPool,
            # `timeout` is forwarded to sqlite3.connect → sets the busy handler so a
            # locked DB waits rather than raising immediately during connect itself.
            "connect_args": {"timeout": _SQLITE_BUSY_TIMEOUT_MS / 1000},
        }
    if getenv("LUMONOX_TEST_PG_ASYNC_NULLPOOL", "").strip().lower() in {"1", "true", "yes"}:
        # Pytest + Starlette ``TestClient`` uses a per-client event loop; pooled asyncpg
        # connections must not be reused across ``asyncio.run`` / sequential clients.
        return {"pool_pre_ping": True, "poolclass": NullPool}

    def _env_int_bounded(
        name: str, *, default: int, minimum: int, maximum: int | None = None
    ) -> int:
        raw = getenv(name)
        if raw is None:
            value = default
        else:
            try:
                value = int(raw.strip())
            except ValueError:
                value = default
        value = max(value, minimum)
        if maximum is not None:
            value = min(value, maximum)
        return value

    return {
        "pool_pre_ping": True,
        "pool_size": _env_int_bounded(
            "LUMONOX_SQLALCHEMY_POOL_SIZE", default=5, minimum=1, maximum=50
        ),
        "max_overflow": _env_int_bounded(
            "LUMONOX_SQLALCHEMY_MAX_OVERFLOW", default=10, minimum=0, maximum=50
        ),
    }


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Read/default engine: deferred ``BEGIN``, so reads stay concurrent under WAL."""
    resolved_database_url = database_url or get_settings().database_url
    engine = _engines.get(resolved_database_url)
    if engine is None:
        pool_kw = _async_pool_kwargs(resolved_database_url)
        engine = create_async_engine(resolved_database_url, **pool_kw)
        if resolved_database_url.startswith("sqlite"):
            event.listen(engine.sync_engine, "connect", _configure_sqlite_connection)
        _engines[resolved_database_url] = engine
    return engine


def get_write_engine(database_url: str | None = None) -> AsyncEngine:
    """Write engine: SQLite transactions open with ``BEGIN IMMEDIATE`` (see module docs).

    For non-SQLite URLs there is nothing to do — Postgres handles concurrent writers
    natively — so the standard engine is reused.
    """
    resolved_database_url = database_url or get_settings().database_url
    if not resolved_database_url.startswith("sqlite"):
        return get_engine(resolved_database_url)
    engine = _write_engines.get(resolved_database_url)
    if engine is None:
        pool_kw = _async_pool_kwargs(resolved_database_url)
        engine = create_async_engine(resolved_database_url, **pool_kw)
        event.listen(engine.sync_engine, "connect", _configure_sqlite_write_connection)
        event.listen(engine.sync_engine, "begin", _begin_immediate)
        _write_engines[resolved_database_url] = engine
    return engine


async def dispose_engine_for_url(database_url: str) -> None:
    """Close all pooled connections so a separate process (or sqlite3) can VACUUM the file."""
    normalized = database_url.strip()
    engine = _engines.pop(normalized, None)
    _session_makers.pop(normalized, None)
    write_engine = _write_engines.pop(normalized, None)
    _write_session_makers.pop(normalized, None)
    if engine is not None:
        await engine.dispose()
    if write_engine is not None:
        await write_engine.dispose()


def dispose_all_cached_async_engines() -> None:
    """Close every cached async engine and session factory (synchronous).

    Integration tests that call :func:`asyncio.run` around job helpers (which use
    :func:`get_session_maker`) can bind asyncpg connections to a short-lived loop.
    Starlette's :class:`TestClient` runs the app on another loop; awaiting
    :meth:`AsyncEngine.dispose` from the main thread then hits "different loop" errors.
    Disposing via the bound :attr:`AsyncEngine.sync_engine` avoids awaiting on the wrong loop.
    """
    entries = list(_engines.items()) + list(_write_engines.items())
    _engines.clear()
    _session_makers.clear()
    _write_engines.clear()
    _write_session_makers.clear()
    for _, engine in entries:
        sync_engine = getattr(engine, "sync_engine", None)
        if sync_engine is not None:
            sync_engine.dispose()


def get_session_maker(
    database_url: str | None = None,
) -> async_sessionmaker_type[AsyncSession]:
    """Session factory on the read/default engine. For writes use ``get_write_session_maker``."""
    resolved_database_url = database_url or get_settings().database_url
    session_maker = _session_makers.get(resolved_database_url)
    if session_maker is None:
        engine = get_engine(resolved_database_url)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        _session_makers[resolved_database_url] = session_maker
    return session_maker


def get_write_session_maker(
    database_url: str | None = None,
) -> async_sessionmaker_type[AsyncSession]:
    """Session factory on the write engine — use for any code path that writes."""
    resolved_database_url = database_url or get_settings().database_url
    session_maker = _write_session_makers.get(resolved_database_url)
    if session_maker is None:
        engine = get_write_engine(resolved_database_url)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        _write_session_makers[resolved_database_url] = session_maker
    return session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped read session. Write paths must open their own ``write_session()``."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


@asynccontextmanager
async def write_session(
    database_url: str | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Short-lived session bound to the write engine — use for any code path that writes.

    The caller still owns the transaction boundary (call ``await session.commit()``);
    on an unhandled exception the session is rolled back on exit as usual. Keep the
    scope tight — under ``BEGIN IMMEDIATE`` the write lock is held for the whole block.
    """
    session_maker = get_write_session_maker(database_url)
    async with session_maker() as session:
        yield session


async def warm_database_connections(database_url: str | None = None) -> None:
    """Open one connection and run ``SELECT 1`` so the first real request skips cold connect."""
    resolved = database_url or get_settings().database_url
    engine = get_engine(resolved)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
