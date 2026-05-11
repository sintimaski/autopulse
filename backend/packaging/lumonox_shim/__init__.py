"""Stable import surface for the ``lumonox`` PyPI distribution (FastAPI API wheel).

Install with ``pip install lumonox`` or ``uv add lumonox``, then use:

    from lumonox import mount_on_app

The implementation lives in ``lumonox_backend``; this module is a thin facade
so the distribution name matches the primary import path.

When ``lumonox-sdk`` is installed together (``pip install "lumonox-sdk[stack]"``),
the SDK owns ``lumonox/__init__.py`` and re-exports the same names from
``lumonox_backend`` so both instrumentation and mounting stay under one module.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from lumonox_backend.app import create_app, mount_on_app

try:
    __version__ = version("lumonox")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["create_app", "mount_on_app", "__version__"]
