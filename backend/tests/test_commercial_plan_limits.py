from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.commercial.plan_limits import (
    effective_ingest_rate_limit_max,
    retention_plan_ingest_rate_multiplier,
)
from lumonox_backend.core.config import normalize_database_url
from lumonox_backend.models import Base, Project, ProjectUiSettings


def test_retention_plan_ingest_rate_multiplier_starter() -> None:
    assert retention_plan_ingest_rate_multiplier("starter") == 0.35


def test_retention_plan_ingest_rate_multiplier_unknown_defaults() -> None:
    assert retention_plan_ingest_rate_multiplier("unknown-tier") == 1.0


def test_retention_plan_ingest_rate_multiplier_extended_matches_standard() -> None:
    assert retention_plan_ingest_rate_multiplier("extended") == 1.0
    assert retention_plan_ingest_rate_multiplier("standard") == 1.0


def test_effective_ingest_rate_limit_scales_by_plan_and_clamps_floor(tmp_path: Path) -> None:
    db_path = tmp_path / "plan_limits.db"
    database_url = normalize_database_url(f"sqlite+aiosqlite:///{db_path}")

    async def run() -> tuple[int, int, int]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            async with session_maker() as session:
                p_starter = Project(id=uuid4(), name="Starter")
                p_std = Project(id=uuid4(), name="Std")
                session.add_all([p_starter, p_std])
                await session.flush()
                session.add_all(
                    [
                        ProjectUiSettings(
                            project_id=p_starter.id,
                            theme_preference="system",
                            retention_plan="starter",
                        ),
                        ProjectUiSettings(
                            project_id=p_std.id,
                            theme_preference="system",
                            retention_plan="standard",
                        ),
                    ]
                )
                await session.commit()
            async with session_maker() as session:
                starter_max = await effective_ingest_rate_limit_max(
                    session, project_id=p_starter.id, base_max_requests=1000
                )
                std_max = await effective_ingest_rate_limit_max(
                    session, project_id=p_std.id, base_max_requests=1000
                )
                tiny_max = await effective_ingest_rate_limit_max(
                    session, project_id=p_starter.id, base_max_requests=12
                )
                return starter_max, std_max, tiny_max
        finally:
            await engine.dispose()

    starter_max, std_max, tiny_max = asyncio.run(run())
    assert starter_max == 350
    assert std_max == 1000
    assert tiny_max == 10
