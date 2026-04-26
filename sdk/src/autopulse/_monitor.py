from __future__ import annotations

from typing import Any


def monitor(app: Any, **kwargs: Any) -> None:
    """Attach AutoPulse monitoring to a FastAPI application.

    Parameters are reserved for future configuration (API key, service name,
    environment, etc.). The scaffold implementation does not modify the app.
    """
    _ = (app, kwargs)
