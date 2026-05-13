"""Environment-variable parsers shared by the SDK's config layer.

These helpers are deliberately permissive: bad values silently fall back to the
caller's default. That matches the SDK's never-break-host-app contract — a
malformed ``LUMONOX_*`` env var must not raise at import or middleware
construction time.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_csv(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _optional_metadata_str(kwargs_val: object, env_name: str, *, max_len: int) -> str | None:
    if isinstance(kwargs_val, str) and kwargs_val.strip():
        return kwargs_val.strip()[:max_len]
    raw = (os.getenv(env_name) or "").strip()
    return raw[:max_len] if raw else None
