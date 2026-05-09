"""Cross-cutting application concerns (config, security hooks, etc.)."""

from __future__ import annotations

from lumonox_backend.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
