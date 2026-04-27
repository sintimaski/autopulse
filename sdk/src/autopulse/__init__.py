"""AutoPulse SDK: FastAPI observability integration."""

from autopulse._monitor import monitor


def autopulse(app: object, **kwargs: object) -> None:
    """One-line setup for embedded local AutoPulse mode."""
    options = dict(kwargs)
    options.setdefault("mode", "embedded")
    monitor(app, **options)


__all__ = ["monitor", "autopulse"]
