from __future__ import annotations

from collections.abc import AsyncGenerator

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

from autopulse_backend.core.config import get_settings

_engines: dict[str, AsyncEngine] = {}
_session_makers: dict[str, async_sessionmaker_type[AsyncSession]] = {}


def get_engine(database_url: str | None = None) -> AsyncEngine:
    resolved_database_url = database_url or get_settings().database_url
    engine = _engines.get(resolved_database_url)
    if engine is None:
        # SQLite: avoid a connection pool so VACUUM can run between requests/retention passes.
        pool_kw: dict = {"pool_pre_ping": True}
        if resolved_database_url.startswith("sqlite"):
            pool_kw = {"poolclass": NullPool}
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
