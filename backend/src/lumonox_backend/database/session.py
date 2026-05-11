from __future__ import annotations

from collections.abc import AsyncGenerator
from os import getenv
from typing import Any

from sqlalchemy import text
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

_engines: dict[str, AsyncEngine] = {}
_session_makers: dict[str, async_sessionmaker_type[AsyncSession]] = {}


def _async_pool_kwargs(database_url: str) -> dict[str, Any]:
    """Connection pool options: NullPool for SQLite; bounded pool for Postgres/async drivers."""
    if database_url.startswith("sqlite"):
        return {"pool_pre_ping": True, "poolclass": NullPool}
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
    resolved_database_url = database_url or get_settings().database_url
    engine = _engines.get(resolved_database_url)
    if engine is None:
        pool_kw = _async_pool_kwargs(resolved_database_url)
        engine = create_async_engine(resolved_database_url, **pool_kw)
        _engines[resolved_database_url] = engine
    return engine


async def dispose_engine_for_url(database_url: str) -> None:
    """Close all pooled connections so a separate process (or sqlite3) can VACUUM the file."""
    normalized = database_url.strip()
    engine = _engines.pop(normalized, None)
    _session_makers.pop(normalized, None)
    if engine is not None:
        await engine.dispose()


def dispose_all_cached_async_engines() -> None:
    """Close every cached async engine and session factory (synchronous).

    Integration tests that call :func:`asyncio.run` around job helpers (which use
    :func:`get_session_maker`) can bind asyncpg connections to a short-lived loop.
    Starlette's :class:`TestClient` runs the app on another loop; awaiting
    :meth:`AsyncEngine.dispose` from the main thread then hits "different loop" errors.
    Disposing via the bound :attr:`AsyncEngine.sync_engine` avoids awaiting on the wrong loop.
    """
    entries = list(_engines.items())
    _engines.clear()
    _session_makers.clear()
    for _, engine in entries:
        sync_engine = getattr(engine, "sync_engine", None)
        if sync_engine is not None:
            sync_engine.dispose()


def get_session_maker(
    database_url: str | None = None,
) -> async_sessionmaker_type[AsyncSession]:
    resolved_database_url = database_url or get_settings().database_url
    session_maker = _session_makers.get(resolved_database_url)
    if session_maker is None:
        engine = get_engine(resolved_database_url)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        _session_makers[resolved_database_url] = session_maker
    return session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def warm_database_connections(database_url: str | None = None) -> None:
    """Open one connection and run ``SELECT 1`` so the first real request skips cold connect."""
    resolved = database_url or get_settings().database_url
    engine = get_engine(resolved)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
