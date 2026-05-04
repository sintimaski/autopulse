from __future__ import annotations

from autopulse_backend.core.config import redact_database_url_for_log


def test_redact_database_url_for_log_strips_password() -> None:
    raw = "postgresql+asyncpg://appuser:supersecret@db.example.com:5432/autopulse"
    redacted = redact_database_url_for_log(raw)
    assert "supersecret" not in redacted
    assert ":***@" in redacted
    assert "db.example.com" in redacted
    assert redacted.startswith("postgresql+asyncpg://")


def test_redact_database_url_for_log_sqlite_unchanged() -> None:
    url = "sqlite+aiosqlite:///./autopulse.db"
    assert redact_database_url_for_log(url) == url
