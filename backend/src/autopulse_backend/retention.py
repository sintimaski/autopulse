from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.config import Settings
from autopulse_backend.models import Event


@dataclass(frozen=True, slots=True)
class RetentionCleanupResult:
    cutoff: datetime
    deleted_events: int


async def run_retention_cleanup_once(
    session: AsyncSession,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> RetentionCleanupResult:
    resolved_now = now.astimezone(UTC) if now is not None else datetime.now(tz=UTC)
    cutoff = resolved_now - timedelta(days=settings.retention_raw_events_days)
    stale_count_result = await session.execute(
        select(func.count(Event.id)).where(Event.received_at < cutoff)
    )
    stale_count = int(stale_count_result.scalar_one())
    if stale_count > 0:
        await session.execute(delete(Event).where(Event.received_at < cutoff))
    await session.commit()
    return RetentionCleanupResult(cutoff=cutoff, deleted_events=stale_count)
