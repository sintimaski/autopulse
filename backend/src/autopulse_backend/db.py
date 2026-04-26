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


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    engine = _engines.get(settings.database_url)
    if engine is None:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _engines[settings.database_url] = engine
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
