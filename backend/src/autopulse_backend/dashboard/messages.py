from __future__ import annotations

from typing import Any


def dashboard_request_log_message(event_type: str, payload: Any) -> str | None:
    """Human-readable diagnostic text for dashboard request rows (error events only)."""
    if not isinstance(payload, dict):
        return None
    if event_type != "error":
        return None
    raw = payload.get("exception_message")
    if raw is None:
        raw = payload.get("message")
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return text[:4000]
