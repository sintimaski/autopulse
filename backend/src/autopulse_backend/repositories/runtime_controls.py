from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.models import IngestRateLimitWindow, SchedulerJobLease

logger = logging.getLogger(__name__)

# Concurrent inserts may collide on unique (project_id, window_start); retry after IntegrityError.
_DISTRIBUTED_INGEST_RL_ATTEMPTS = 16


def _window_start(now: datetime, *, window_seconds: int) -> datetime:
    unix_seconds = int(now.timestamp())
    bucket = unix_seconds - (unix_seconds % max(1, window_seconds))
    return datetime.fromtimestamp(bucket, tz=UTC)


async def allow_distributed_ingest_request(
    *,
    session: AsyncSession,
    project_id: UUID,
    max_requests: int,
    window_seconds: int,
    now: datetime | None = None,
) -> bool:
    if max_requests <= 0:
        return True
    resolved_now = now or datetime.now(tz=UTC)
    bucket_start = _window_start(resolved_now, window_seconds=window_seconds)
    cutoff = resolved_now - timedelta(seconds=max(1, window_seconds * 2))
    for _ in range(_DISTRIBUTED_INGEST_RL_ATTEMPTS):
        await session.execute(
            delete(IngestRateLimitWindow).where(IngestRateLimitWindow.window_start < cutoff)
        )
        row = await session.scalar(
            select(IngestRateLimitWindow).where(
                IngestRateLimitWindow.project_id == project_id,
                IngestRateLimitWindow.window_start == bucket_start,
            )
        )
        if row is None:
            session.add(
                IngestRateLimitWindow(
                    project_id=project_id,
                    window_start=bucket_start,
                    request_count=1,
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                continue

        if row.request_count >= max_requests:
            await session.rollback()
            return False

        row.request_count += 1
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            continue

    logger.warning(
        "distributed_ingest_rate_limit_retry_exhausted",
        extra={
            "event": "distributed_ingest_rate_limit_retry_exhausted",
            "project_id": str(project_id),
            "attempts": _DISTRIBUTED_INGEST_RL_ATTEMPTS,
        },
    )
    # Surfaces to ingest as distributed limiter failure → in-memory fallback (fail-open).
    raise RuntimeError("distributed ingest rate limit contention exceeded retry budget") from None


async def acquire_scheduler_lease(
    *,
    session: AsyncSession,
    job_name: str,
    owner_token: str,
    lease_ttl_seconds: int,
    now: datetime | None = None,
) -> bool:
    resolved_now = now or datetime.now(tz=UTC)
    expires_at = resolved_now + timedelta(seconds=max(5, lease_ttl_seconds))
    lease = await session.scalar(
        select(SchedulerJobLease).where(SchedulerJobLease.job_name == job_name)
    )
    if lease is None:
        session.add(
            SchedulerJobLease(
                job_name=job_name,
                owner_token=owner_token,
                lease_expires_at=expires_at,
            )
        )
        await session.commit()
        return True
    if lease.owner_token == owner_token or lease.lease_expires_at <= resolved_now:
        lease.owner_token = owner_token
        lease.lease_expires_at = expires_at
        await session.commit()
        return True
    await session.rollback()
    return False
