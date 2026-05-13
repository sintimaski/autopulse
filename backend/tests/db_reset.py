"""Shared database reset helpers for backend integration-style tests."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_FULL_RESET_TABLES = (
    "alert_webhook_pacing",
    "alert_dispatches",
    "project_alert_settings",
    "ingest_sql_tail_repair_items",
    "ingest_aggregate_dead_letters",
    "ingest_idempotency_keys",
    "ingest_rate_limit_windows",
    "error_group_aggregates",
    "metric_buckets",
    "events",
    "api_keys",
    "projects",
)

_INGEST_CORE_TABLES = (
    "ingest_sql_tail_repair_items",
    "ingest_aggregate_dead_letters",
    "ingest_idempotency_keys",
    "ingest_rate_limit_windows",
    "error_group_aggregates",
    "metric_buckets",
    "events",
    "api_keys",
    "projects",
)


def _postgres_truncate_sql(tables: tuple[str, ...]) -> text:
    return text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE")


async def _truncate_tables_async(
    session: AsyncSession, database_url: str, tables: tuple[str, ...]
) -> None:
    if "sqlite" in database_url.lower():
        res = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        existing = {str(row[0]) for row in res.fetchall()}
        await session.execute(text("PRAGMA foreign_keys=OFF"))
        for table in tables:
            if table in existing:
                await session.execute(text(f"DELETE FROM {table}"))
        await session.execute(text("PRAGMA foreign_keys=ON"))
    else:
        await session.execute(_postgres_truncate_sql(tables))


def truncate_full_schema(database_url: str) -> None:
    """Remove all rows from MVP tables (projects, keys, events, alert state)."""

    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                await _truncate_tables_async(session, database_url, _FULL_RESET_TABLES)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def truncate_ingest_core_tables(database_url: str) -> None:
    """Clear tables used by ingest/dashboard-style integration tests."""

    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                await _truncate_tables_async(session, database_url, _INGEST_CORE_TABLES)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())
