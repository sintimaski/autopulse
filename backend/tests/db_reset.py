"""Shared database reset helpers for backend integration-style tests."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_FULL_RESET_SQL = text(
    "TRUNCATE TABLE alert_dispatches, project_alert_settings, "
    "error_group_aggregates, metric_buckets, events, api_keys, projects "
    "RESTART IDENTITY CASCADE"
)


def truncate_full_schema(database_url: str) -> None:
    """Remove all rows from MVP tables (projects, keys, events, alert state)."""

    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                await session.execute(_FULL_RESET_SQL)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())
