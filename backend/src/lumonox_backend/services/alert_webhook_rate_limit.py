"""Process-local pacing for outbound alert webhook POSTs (per normalized URL)."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlsplit

_webhook_url_lock = asyncio.Lock()
_webhook_url_last_monotonic: dict[str, float] = {}


def _normalize_webhook_rate_key(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "").lower()
    netloc = (parts.netloc or "").lower()
    if netloc:
        return f"{scheme}://{netloc}"
    return url.strip().lower()


async def throttle_alert_webhook_url(url: str, min_interval_seconds: float) -> None:
    if min_interval_seconds <= 0:
        return
    key = _normalize_webhook_rate_key(url)
    if not key:
        return
    async with _webhook_url_lock:
        now = time.monotonic()
        last = _webhook_url_last_monotonic.get(key, 0.0)
        wait_s = min_interval_seconds - (now - last)
        if wait_s > 0:
            await asyncio.sleep(wait_s)
        _webhook_url_last_monotonic[key] = time.monotonic()


__all__ = ["throttle_alert_webhook_url"]
