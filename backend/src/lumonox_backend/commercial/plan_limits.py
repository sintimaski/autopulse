from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.models import ProjectUiSettings

_RETENTION_PLAN_INGEST_RATE_MULTIPLIER: dict[str, float] = {
    "starter": 0.35,
    "standard": 1.0,
    "extended": 1.0,
}


def retention_plan_ingest_rate_multiplier(plan: str | None) -> float:
    """Public helper for unit tests and documentation of tier multipliers."""
    normalized = (plan or "standard").strip().lower()
    return _RETENTION_PLAN_INGEST_RATE_MULTIPLIER.get(normalized, 1.0)


async def effective_ingest_rate_limit_max(
    session: AsyncSession,
    *,
    project_id: UUID,
    base_max_requests: int,
) -> int:
    """Scale ingest rate limit window max by ``project_ui_settings.retention_plan`` tier."""
    plan = await session.scalar(
        select(ProjectUiSettings.retention_plan).where(ProjectUiSettings.project_id == project_id)
    )
    multiplier = retention_plan_ingest_rate_multiplier(plan)
    return max(10, int(base_max_requests * multiplier))
