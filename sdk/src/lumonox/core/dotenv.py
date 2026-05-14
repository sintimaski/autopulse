"""Tiny zero-dependency ``.env`` loader for the SDK's config layer.

Pip-installed users want the SDK to be a one-line addition: ``lumonox(app)``
plus a ``.env`` next to their app — no shell exports, no ``python-dotenv`` /
``pydantic-settings`` wiring of their own. The SDK ships no config dependency
and must never break the host app, so this loader is deliberately narrow:

* only ``LUMONOX_*`` keys are read — unrelated host config is never touched;
* values already in the environment are never overridden — shell / host
  config always wins, so it is safe to call repeatedly;
* every error (missing file, bad encoding, malformed line) is swallowed.

Opt out with ``lumonox(app, load_dotenv=False)`` or point at a specific file
with ``lumonox(app, dotenv_path="/path/to/.env")``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("lumonox.monitor")

_PREFIX = "LUMONOX_"
_MAX_PARENT_WALK = 4


def _find_dotenv(explicit: str | None) -> Path | None:
    """Resolve the ``.env`` to read: an explicit path, else cwd + a few parents."""
    if explicit:
        candidate = Path(explicit).expanduser()
        return candidate if candidate.is_file() else None
    here = Path.cwd()
    for directory in (here, *list(here.parents)[:_MAX_PARENT_WALK]):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def _parse_dotenv(text: str) -> dict[str, str]:
    """Parse ``KEY=value`` lines, keeping only ``LUMONOX_*`` keys.

    Supports ``#`` comments, optional ``export`` prefix, and single/double
    quoted values. Anything it does not understand is skipped, not raised.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key.startswith(_PREFIX):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def load_lumonox_dotenv(path: str | None = None) -> int:
    """Load ``LUMONOX_*`` keys from a ``.env`` file into ``os.environ``.

    Returns the number of keys set. Existing environment values are never
    overridden. Never raises — a missing or malformed file is a silent no-op.
    """
    try:
        dotenv_path = _find_dotenv(path)
        if dotenv_path is None:
            return 0
        parsed = _parse_dotenv(dotenv_path.read_text(encoding="utf-8"))
        loaded = 0
        for key, value in parsed.items():
            if key not in os.environ:
                os.environ[key] = value
                loaded += 1
        if loaded:
            logger.debug("lumonox: loaded %d LUMONOX_* var(s) from %s", loaded, dotenv_path)
        return loaded
    except Exception:  # noqa: BLE001 - config discovery must never break the host app
        return 0
