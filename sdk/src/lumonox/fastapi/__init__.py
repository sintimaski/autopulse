"""FastAPI / Starlette adapter for the Lumonox SDK.

The public entry points (``monitor`` / ``lumonox``) live on the top-level
``lumonox`` namespace and continue to be re-exported there. ``lumonox.fastapi``
is the canonical home for the adapter implementation; see
``sdk/docs/adapters.md`` for the contract a framework adapter must honor.
"""

from lumonox.fastapi.middleware import monitor

__all__ = ["monitor"]
