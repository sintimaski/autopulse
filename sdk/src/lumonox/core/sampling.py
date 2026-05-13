"""Deterministic request sampling.

Sampling is keyed off the correlation id (or a stable hash of method+path+time
when no id is available) so a single request is either fully captured or
fully skipped — important when the dashboard renders error rate alongside the
request stream. 5xx responses always bypass the sampler (see middleware).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def _clamp_sample_rate(value: float) -> float:
    return min(1.0, max(0.0, value))


def _should_sample_request(
    *,
    request_sample_rate: float,
    method: str,
    path: str,
    request_id: str | None,
) -> bool:
    if request_sample_rate >= 1.0:
        return True
    if request_sample_rate <= 0.0:
        return False
    if request_id and request_id.strip():
        key = request_id.strip()
    else:
        now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
        key = f"{method}:{path}:{now_iso}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    fraction = int.from_bytes(digest[:8], byteorder="big", signed=False) / float(1 << 64)
    return fraction < request_sample_rate
