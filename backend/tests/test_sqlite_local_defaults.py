"""Settings defaults for workspace-local SQLite (dev default filenames)."""

from __future__ import annotations

from pathlib import Path

import pytest

import autopulse_backend.core.config as _config


@pytest.fixture(autouse=True)
def _disable_runtime_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not load ``backend/.env`` here; local developer env would override test env vars."""

    def _noop_load_runtime_dotenv() -> None:
        if _config._RUNTIME_DOTENV_LOADED:
            return
        _config._RUNTIME_DOTENV_LOADED = True

    monkeypatch.setattr(_config, "_load_runtime_dotenv_once", _noop_load_runtime_dotenv)
    monkeypatch.setattr(_config, "_RUNTIME_DOTENV_LOADED", False)


def test_autopulse_db_url_enables_retention_scheduler_and_default_file_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JOBS_ENABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("AUTOPULSE_SQLITE_MAX_DB_FILE_MB", raising=False)
    monkeypatch.delenv("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB", raising=False)
    monkeypatch.delenv("JOBS_RETENTION_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse.db")

    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    assert settings.jobs_enable_scheduler is True
    assert settings.sqlite_max_db_file_mb == 512
    assert settings.jobs_retention_interval_seconds <= 300.0
    assert settings.retention_pressure_poll_seconds == 1.0


def test_autopulse_legacy_embedded_db_filename_gets_same_retention_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JOBS_ENABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("AUTOPULSE_SQLITE_MAX_DB_FILE_MB", raising=False)
    monkeypatch.delenv("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB", raising=False)
    monkeypatch.delenv("JOBS_RETENTION_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse_embedded.db")

    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    assert settings.jobs_enable_scheduler is True
    assert settings.sqlite_max_db_file_mb == 512
    assert settings.retention_pressure_poll_seconds == 1.0


def test_jobs_retention_interval_seconds_accepts_five_second_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBS_RETENTION_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse.db")

    from autopulse_backend.core.config import get_settings

    assert get_settings().jobs_retention_interval_seconds == 5.0


def test_autopulse_db_explicit_jobs_scheduler_false_stays_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse.db")
    monkeypatch.setenv("JOBS_ENABLE_SCHEDULER", "false")
    monkeypatch.delenv("AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS", raising=False)

    from autopulse_backend.core.config import get_settings

    assert get_settings().jobs_enable_scheduler is False


def test_explicit_zero_retention_pressure_poll_disables_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JOBS_ENABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("AUTOPULSE_SQLITE_MAX_DB_FILE_MB", raising=False)
    monkeypatch.delenv("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse.db")
    monkeypatch.setenv("AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS", "0")

    from autopulse_backend.core.config import get_settings

    assert get_settings().retention_pressure_poll_seconds == 0.0


def test_custom_sqlite_filename_does_not_auto_enable_scheduler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "custom_events.db"
    monkeypatch.delenv("JOBS_ENABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("AUTOPULSE_SQLITE_MAX_DB_FILE_MB", raising=False)
    monkeypatch.delenv("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB", raising=False)
    monkeypatch.delenv("AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    assert settings.jobs_enable_scheduler is False
    assert settings.sqlite_max_db_file_mb is None
    assert settings.retention_pressure_poll_seconds == 0.0
