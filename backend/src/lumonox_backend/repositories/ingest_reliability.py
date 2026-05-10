from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.models import (
    IngestAggregateDeadLetter,
    IngestIdempotencyKey,
    IngestSqlTailRepairItem,
)
from lumonox_backend.repositories.aggregates import ErrorGroupAggregateDelta, MetricBucketDelta
from lumonox_backend.services.aggregate_delta_codec import encode_aggregate_payload

logger = logging.getLogger(__name__)


def summarize_exception_for_persistence(exc: BaseException) -> str:
    """Return a stable, non-sensitive error summary for DB persistence."""
    name = exc.__class__.__name__.strip()
    if not name:
        return "UnknownError"
    return name[:128]


def hash_idempotency_key(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


async def insert_aggregate_dead_letter(
    session: AsyncSession,
    *,
    metric_bucket_deltas: list[MetricBucketDelta],
    error_group_deltas: list[ErrorGroupAggregateDelta],
    last_error: str | None,
) -> None:
    payload: dict[str, Any] = encode_aggregate_payload(
        metric_bucket_deltas=metric_bucket_deltas,
        error_group_deltas=error_group_deltas,
    )
    session.add(
        IngestAggregateDeadLetter(
            payload=payload,
            last_error=last_error,
        )
    )
    await session.commit()


async def fetch_pending_dead_letters(
    session: AsyncSession, *, limit: int = 50
) -> list[IngestAggregateDeadLetter]:
    stmt = (
        select(IngestAggregateDeadLetter)
        .where(IngestAggregateDeadLetter.replayed_at.is_(None))
        .order_by(IngestAggregateDeadLetter.id.asc())
        .limit(limit)
    )
    rows = (await session.scalars(stmt)).all()
    return list(rows)


async def mark_dead_letter_replayed(session: AsyncSession, row_id: int) -> None:
    await session.execute(
        update(IngestAggregateDeadLetter)
        .where(IngestAggregateDeadLetter.id == row_id)
        .values(replayed_at=datetime.now(tz=UTC))
    )
    await session.commit()


async def insert_sql_tail_repair_item(
    session: AsyncSession,
    *,
    project_id: UUID,
    payload: dict[str, Any],
    last_error: str | None,
) -> None:
    session.add(
        IngestSqlTailRepairItem(
            project_id=project_id,
            payload=payload,
            last_error=last_error,
        )
    )
    await session.commit()


async def fetch_pending_sql_tail_repair_items(
    session: AsyncSession, *, limit: int = 50
) -> list[IngestSqlTailRepairItem]:
    now = datetime.now(tz=UTC)
    stmt = (
        select(IngestSqlTailRepairItem)
        .where(
            IngestSqlTailRepairItem.resolved_at.is_(None),
            IngestSqlTailRepairItem.dead_lettered_at.is_(None),
            IngestSqlTailRepairItem.next_retry_at <= now,
        )
        .order_by(IngestSqlTailRepairItem.id.asc())
        .limit(limit)
    )
    rows = (await session.scalars(stmt)).all()
    return list(rows)


async def mark_sql_tail_repair_resolved(session: AsyncSession, row_id: int) -> None:
    now = datetime.now(tz=UTC)
    await session.execute(
        update(IngestSqlTailRepairItem)
        .where(IngestSqlTailRepairItem.id == row_id)
        .values(
            resolved_at=now,
            last_attempt_at=now,
            last_error=None,
        )
    )
    await session.commit()


async def mark_sql_tail_repair_retry(
    session: AsyncSession,
    *,
    row_id: int,
    attempt_count: int,
    next_retry_at: datetime,
    last_error: str,
    dead_lettered: bool,
) -> None:
    now = datetime.now(tz=UTC)
    values: dict[str, Any] = {
        "attempt_count": max(0, int(attempt_count)),
        "last_attempt_at": now,
        "next_retry_at": next_retry_at,
        "last_error": last_error[:2048],
    }
    if dead_lettered:
        values["dead_lettered_at"] = now
    await session.execute(
        update(IngestSqlTailRepairItem).where(IngestSqlTailRepairItem.id == row_id).values(**values)
    )
    await session.commit()


async def get_completed_idempotency_accepted(
    session: AsyncSession, *, project_id: UUID, key_hash: str
) -> int | None:
    row = await session.scalar(
        select(IngestIdempotencyKey).where(
            IngestIdempotencyKey.project_id == project_id,
            IngestIdempotencyKey.key_hash == key_hash,
            IngestIdempotencyKey.expires_at > datetime.now(tz=UTC),
        )
    )
    if row is None:
        return None
    if row.accepted_events is None:
        return None
    return int(row.accepted_events)


async def delete_idempotency_row(session: AsyncSession, *, project_id: UUID, key_hash: str) -> None:
    await session.execute(
        delete(IngestIdempotencyKey).where(
            IngestIdempotencyKey.project_id == project_id,
            IngestIdempotencyKey.key_hash == key_hash,
        )
    )
    await session.commit()


async def reserve_idempotency_key(
    session: AsyncSession,
    *,
    project_id: UUID,
    key_hash: str,
    ttl_hours: int,
    stale_seconds: int,
) -> Literal["reserved", "duplicate", "conflict"]:
    """Reserve a pending idempotency row for ``POST /ingest``."""
    now = datetime.now(tz=UTC)
    expires_at = now + timedelta(hours=max(1, ttl_hours))

    for _ in range(5):
        existing = await session.scalar(
            select(IngestIdempotencyKey).where(
                IngestIdempotencyKey.project_id == project_id,
                IngestIdempotencyKey.key_hash == key_hash,
            )
        )
        if existing is not None and existing.expires_at <= now:
            await session.execute(
                delete(IngestIdempotencyKey).where(IngestIdempotencyKey.id == existing.id)
            )
            await session.commit()
            existing = None

        if existing is not None and existing.accepted_events is not None:
            return "duplicate"

        if existing is not None and existing.accepted_events is None:
            age = (now - existing.reserved_at).total_seconds()
            if age <= stale_seconds:
                return "conflict"
            await session.execute(
                delete(IngestIdempotencyKey).where(IngestIdempotencyKey.id == existing.id)
            )
            await session.commit()

        try:
            session.add(
                IngestIdempotencyKey(
                    project_id=project_id,
                    key_hash=key_hash,
                    accepted_events=None,
                    reserved_at=now,
                    expires_at=expires_at,
                )
            )
            await session.commit()
            return "reserved"
        except IntegrityError:
            await session.rollback()
            continue

    logger.warning("ingest_idempotency_integrity_race_unresolved")
    return "conflict"


async def complete_idempotency_key(
    session: AsyncSession, *, project_id: UUID, key_hash: str, accepted_events: int
) -> None:
    await session.execute(
        update(IngestIdempotencyKey)
        .where(
            IngestIdempotencyKey.project_id == project_id,
            IngestIdempotencyKey.key_hash == key_hash,
            IngestIdempotencyKey.accepted_events.is_(None),
        )
        .values(accepted_events=accepted_events)
    )
    await session.commit()


async def release_idempotency_reservation(
    session: AsyncSession, *, project_id: UUID, key_hash: str
) -> None:
    await session.execute(
        delete(IngestIdempotencyKey).where(
            IngestIdempotencyKey.project_id == project_id,
            IngestIdempotencyKey.key_hash == key_hash,
            IngestIdempotencyKey.accepted_events.is_(None),
        )
    )
    await session.commit()
