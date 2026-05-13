"""Pacing for outbound alert webhook POSTs (per normalized URL).

Two strategies, picked at runtime:

* **DB-coordinated** (preferred): an ``alert_webhook_pacing`` row tracks the
  reserved next-send instant per webhook key. The reservation update runs in
  a short transaction so multiple API replicas pacing the same webhook agree
  on the global minimum interval.
* **Process-local fallback**: in-memory dict guarded by ``asyncio.Lock``.
  Used when no session maker is available (early startup, unit tests that
  don't touch the DB).

Both strategies sleep the calling task until the next allowed send instant.
This module is intentionally fail-safe — any DB error degrades to the local
strategy rather than dropping the send.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from lumonox_backend.database.session import get_session_maker
from lumonox_backend.models import AlertWebhookPacing

_logger = logging.getLogger(__name__)
_webhook_url_lock = asyncio.Lock()
_webhook_url_last_monotonic: dict[str, float] = {}

# Cap the sleep we will perform on the calling task so a misconfigured pacing
# row (clock skew, accidental far-future reservation) cannot block alert
# delivery indefinitely.
_MAX_PACING_SLEEP_SECONDS = 60.0


def _normalize_webhook_rate_key(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "").lower()
    netloc = (parts.netloc or "").lower()
    if netloc:
        return f"{scheme}://{netloc}"
    return url.strip().lower()


def _db_webhook_key(url: str) -> str:
    """Stable opaque key for the pacing table.

    Hashes the normalized scheme://host so any userinfo/credentials embedded
    in the URL never land in storage in plaintext.
    """
    return hashlib.sha256(_normalize_webhook_rate_key(url).encode("utf-8")).hexdigest()


async def _process_local_throttle(url: str, min_interval_seconds: float) -> None:
    key = _normalize_webhook_rate_key(url)
    if not key:
        return
    async with _webhook_url_lock:
        now = time.monotonic()
        last = _webhook_url_last_monotonic.get(key, 0.0)
        wait_s = min_interval_seconds - (now - last)
        if wait_s > 0:
            await asyncio.sleep(min(wait_s, _MAX_PACING_SLEEP_SECONDS))
        _webhook_url_last_monotonic[key] = time.monotonic()


async def _db_coordinated_throttle(url: str, min_interval_seconds: float) -> bool:
    """Return ``True`` on success (sleep performed if needed); ``False`` to fall back."""
    key = _db_webhook_key(url)
    if not key:
        return False
    try:
        session_maker = get_session_maker()
    except Exception:  # pragma: no cover - settings/engine not configured
        return False
    try:
        async with session_maker() as session:
            now = datetime.now(tz=UTC)
            row = await session.scalar(
                select(AlertWebhookPacing).where(AlertWebhookPacing.webhook_key == key)
            )
            if row is None:
                session.add(AlertWebhookPacing(webhook_key=key, last_sent_at=now))
                await session.commit()
                return True
            last_sent_at = row.last_sent_at
            if last_sent_at.tzinfo is None:
                last_sent_at = last_sent_at.replace(tzinfo=UTC)
            elapsed = (now - last_sent_at).total_seconds()
            wait_s = max(0.0, min_interval_seconds - elapsed)
            # Reserve the next send slot before sleeping so concurrent
            # replicas see a fresh reservation and queue behind it.
            row.last_sent_at = now + timedelta(seconds=wait_s)
            await session.commit()
    except SQLAlchemyError as exc:
        _logger.debug("alert webhook DB pacing degraded: %s", exc)
        return False
    if wait_s > 0:
        await asyncio.sleep(min(wait_s, _MAX_PACING_SLEEP_SECONDS))
    return True


async def throttle_alert_webhook_url(url: str, min_interval_seconds: float) -> None:
    """Sleep until the next allowed send time for ``url``.

    Tries DB-coordinated pacing first and falls back to a process-local lock
    if the DB is unavailable. Returns immediately when pacing is disabled
    (``min_interval_seconds <= 0``).
    """
    if min_interval_seconds <= 0:
        return
    if not _normalize_webhook_rate_key(url):
        return
    if await _db_coordinated_throttle(url, min_interval_seconds):
        return
    await _process_local_throttle(url, min_interval_seconds)


__all__ = ["throttle_alert_webhook_url"]
