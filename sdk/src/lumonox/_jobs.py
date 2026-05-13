"""Backward-compatible re-export shim.

The canonical implementation lives in ``lumonox.core.jobs``.
"""

from lumonox.core.jobs import capture_background_job

__all__ = ["capture_background_job"]
