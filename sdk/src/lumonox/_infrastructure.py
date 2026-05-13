"""Backward-compatible re-export shim.

The canonical implementation lives in ``lumonox.core.infrastructure``;
``lumonox._infrastructure.InfrastructureSampler`` is preserved as an alias so
older callers keep working without modification. New code should import from
``lumonox.core.infrastructure``.

This module is intentionally minimal. Tests that want to stub ``psutil`` should
do so on the canonical path (``lumonox.core.infrastructure.psutil``); the
underscore path no longer carries its own module-level ``psutil`` reference.
"""

from lumonox.core.infrastructure import InfrastructureSampler

__all__ = ["InfrastructureSampler"]
