"""Request-scoped context for Lumonox SDK (correlation IDs, etc.)."""

from __future__ import annotations

from contextvars import ContextVar, Token

# Populated for the duration of each HTTP request handled by Lumonox middleware.
_lumonox_correlation_id: ContextVar[str | None] = ContextVar("lumonox_correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _lumonox_correlation_id.get()


def set_correlation_id(value: str | None) -> Token[str | None]:
    """Return the ContextVar token for ``reset_correlation_id``."""
    return _lumonox_correlation_id.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    _lumonox_correlation_id.reset(token)
