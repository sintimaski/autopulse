"""Backward-compatible re-export shim.

The canonical implementation lives in ``lumonox.core.runtime_context``.
"""

from lumonox.core.runtime_context import (
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

__all__ = ["get_correlation_id", "reset_correlation_id", "set_correlation_id"]
