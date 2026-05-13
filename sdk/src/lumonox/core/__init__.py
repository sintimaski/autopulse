"""Framework-agnostic core for the Lumonox SDK.

Modules under ``lumonox.core`` carry no FastAPI/Starlette imports so a future
framework adapter (Flask, Litestar, …) can reuse the same queue / transport /
scrubbing / event-shape primitives. See ``sdk/docs/adapters.md``.
"""
