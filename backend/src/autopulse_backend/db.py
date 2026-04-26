from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from autopulse_backend.config import get_settings

_engines: dict[str, AsyncEngine] = {}


def get_engine(database_url: str | None = None) -> AsyncEngine:
    resolved_database_url = database_url or get_settings().database_url
    engine = _engines.get(resolved_database_url)
    if engine is None:
        engine = create_async_engine(resolved_database_url, pool_pre_ping=True)
        _engines[resolved_database_url] = engine
    return engine


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = get_engine()
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
