"""Path / prefix normalization used by ignore-list and mount-prefix logic.

Pure functions — no framework dependencies — so adapters for other frameworks
can reuse the exact filter behavior (``LUMONOX_IGNORE_PATH_PREFIXES`` defaults,
mount-prefix handling for the dashboard sub-mount, etc.).
"""

from __future__ import annotations

from lumonox.core.env import _env_csv


def _normalize_mount_prefix(raw: object | None) -> str | None:
    if raw is None:
        return None
    prefix = str(raw).strip()
    if not prefix:
        return None
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    if prefix != "/":
        prefix = prefix.rstrip("/")
    return prefix if prefix != "/" else None


def _normalize_path_prefix(prefix: str) -> str:
    cleaned = str(prefix).strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    if cleaned != "/":
        cleaned = cleaned.rstrip("/")
    return cleaned


def _resolve_ignore_path_prefixes(raw: object | None) -> tuple[str, ...]:
    if raw is None:
        return tuple(
            prefix
            for prefix in (
                _normalize_path_prefix(value)
                for value in _env_csv("LUMONOX_IGNORE_PATH_PREFIXES", "/health,/ready")
            )
            if prefix
        )
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, list | tuple | set):
        candidates = [str(value) for value in raw]
    else:
        return ()
    normalized = []
    for candidate in candidates:
        for part in candidate.split(","):
            prefix = _normalize_path_prefix(part)
            if prefix:
                normalized.append(prefix)
    return tuple(dict.fromkeys(normalized))


def _path_is_ignored(path: str, ignore_path_prefixes: tuple[str, ...]) -> bool:
    if not ignore_path_prefixes:
        return False
    return any(path.startswith(prefix) for prefix in ignore_path_prefixes)
