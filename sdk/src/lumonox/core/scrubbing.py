"""Sensitive-data scrubbing for ingest payloads.

Run on the request thread immediately before ``_EventDispatcher.enqueue``: the
goal is that anything that lands in the bounded queue (and therefore anything
that might be sent on the wire) has already had auth headers, cookies, tokens,
and API keys replaced with ``[REDACTED]``. Adapters for other frameworks share
this exact contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_SCRUB_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "x-api-key",
        "access_token",
        "refresh_token",
    }
)


def _is_sensitive_key(key: str, scrub_keys: frozenset[str]) -> bool:
    lowered = key.lower()
    if lowered in scrub_keys:
        return True
    return any(
        marker in lowered
        for marker in (
            "token",
            "secret",
            "password",
            "passwd",
            "api_key",
            "apikey",
            "api-key",
            "authorization",
            "cookie",
        )
    )


def _scrub_value(value: Any, scrub_keys: frozenset[str]) -> Any:
    if isinstance(value, Mapping):
        return {
            key: (
                "[REDACTED]"
                if _is_sensitive_key(key, scrub_keys)
                else _scrub_value(item, scrub_keys)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_value(item, scrub_keys) for item in value]
    return value
