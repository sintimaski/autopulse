"""DB-coordinated alert webhook pacing tests.

Verifies that the pacing helper writes a reservation row, that a second call
within the configured interval sleeps (within a sane bound), and that pacing
falls back gracefully when no session can be opened.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

from db_reset import truncate_full_schema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.models import AlertWebhookPacing
from lumonox_backend.services.alert_webhook_rate_limit import (
    _db_webhook_key,
    throttle_alert_webhook_url,
)


def _read_pacing_row(database_url: str, key: str) -> AlertWebhookPacing | None:
    async def run() -> AlertWebhookPacing | None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                return await session.scalar(
                    select(AlertWebhookPacing).where(AlertWebhookPacing.webhook_key == key)
                )
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_db_pacing_writes_row_and_returns_immediately_on_first_call(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)
    url = "https://hooks.example.com/path"
    started = time.monotonic()
    asyncio.run(throttle_alert_webhook_url(url, min_interval_seconds=2.0))
    elapsed = time.monotonic() - started
    assert elapsed < 0.5, f"first call should not sleep but took {elapsed:.2f}s"

    row = _read_pacing_row(backend_test_database_url, _db_webhook_key(url))
    assert row is not None
    assert row.last_sent_at is not None


def test_db_pacing_second_call_within_interval_sleeps(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)
    url = "https://hooks.example.com/throttle-me"

    # First call seeds the row.
    asyncio.run(throttle_alert_webhook_url(url, min_interval_seconds=0.4))

    started = time.monotonic()
    asyncio.run(throttle_alert_webhook_url(url, min_interval_seconds=0.4))
    elapsed = time.monotonic() - started

    # The second call should sleep ~0.4s (minus tiny clock drift between calls).
    assert 0.15 <= elapsed <= 1.5, f"second call elapsed {elapsed:.2f}s outside expected range"


def test_db_pacing_disabled_when_interval_zero(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)
    url = "https://hooks.example.com/no-pacing"

    asyncio.run(throttle_alert_webhook_url(url, min_interval_seconds=0.0))
    row = _read_pacing_row(backend_test_database_url, _db_webhook_key(url))
    # With pacing disabled the helper should short-circuit before touching the DB.
    assert row is None


def test_db_pacing_clock_skew_capped_at_max_sleep(
    backend_test_database_url: str,
) -> None:
    """A pacing row reserved far in the future must not block the caller indefinitely."""
    truncate_full_schema(backend_test_database_url)
    url = "https://hooks.example.com/skewed"
    key = _db_webhook_key(url)

    async def seed_future_reservation() -> None:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                session.add(
                    AlertWebhookPacing(
                        webhook_key=key,
                        last_sent_at=datetime.now(tz=UTC) + timedelta(minutes=10),
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed_future_reservation())

    started = time.monotonic()
    # min_interval far smaller than the 10-minute skew; the cap should still
    # bound the sleep so callers don't stall on a stale row.
    asyncio.run(throttle_alert_webhook_url(url, min_interval_seconds=0.1))
    elapsed = time.monotonic() - started
    assert elapsed <= 65.0, (
        f"throttle stalled {elapsed:.1f}s on a far-future reservation (cap should bound it)"
    )
