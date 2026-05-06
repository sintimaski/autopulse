from __future__ import annotations

from pathlib import Path

import pytest

import autopulse_backend.core.config as _config
import autopulse_backend.core.config_env as _config_env


@pytest.fixture(autouse=True)
def _disable_runtime_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not load developer-specific backend/.env during tests."""

    def _noop_load_runtime_dotenv() -> None:
        if _config_env._RUNTIME_DOTENV_LOADED:
            return
        _config_env._RUNTIME_DOTENV_LOADED = True

    monkeypatch.setattr(_config, "_load_runtime_dotenv_once", _noop_load_runtime_dotenv)
    monkeypatch.setattr(_config_env, "_RUNTIME_DOTENV_LOADED", False)


def test_event_plane_mode_defaults_to_single_writer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTOPULSE_EVENT_PLANE_MODE", raising=False)
    monkeypatch.delenv("AUTOPULSE_EVENT_PLANE_SHARDS_PATH", raising=False)
    monkeypatch.delenv("AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH", raising=False)
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")

    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    assert settings.event_plane_mode == "duckdb_single_writer"
    assert settings.event_plane_shards_path.endswith("/.autopulse/events-log")
    assert settings.event_plane_snapshots_path.endswith("/.autopulse/events-duckdb")


def test_event_plane_log_shards_mode_allowed_with_duckdb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_MODE", "duckdb_log_shards")
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")

    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    assert settings.event_plane_mode == "duckdb_log_shards"
    assert settings.event_store == "duckdb"


def test_event_plane_log_shards_mode_rejects_non_duckdb_event_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_MODE", "duckdb_log_shards")
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "sqlite")

    from autopulse_backend.core.config import get_settings

    with pytest.raises(ValueError, match="duckdb_log_shards requires AUTOPULSE_EVENT_STORE=duckdb"):
        get_settings()


def test_event_plane_mode_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_MODE", "banana")
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")

    from autopulse_backend.core.config import get_settings

    with pytest.raises(ValueError, match="AUTOPULSE_EVENT_PLANE_MODE must be one of"):
        get_settings()


def test_event_plane_shards_path_cannot_escape_data_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUTOPULSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_SHARDS_PATH", "../outside")

    from autopulse_backend.core.config import get_settings

    with pytest.raises(ValueError, match="AUTOPULSE_EVENT_PLANE_SHARDS_PATH"):
        get_settings()


def test_event_plane_snapshots_path_cannot_escape_data_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUTOPULSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH", "../outside")

    from autopulse_backend.core.config import get_settings

    with pytest.raises(ValueError, match="AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH"):
        get_settings()


def test_event_plane_backpressure_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_MODE", "duckdb_log_shards")
    monkeypatch.setenv("AUTOPULSE_COMPACTOR_MAX_SHARDS_PER_RUN", "77")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MIN_FREE_BYTES", "12345")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MIN_FREE_PERCENT", "7")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MAX_PENDING_SHARDS", "222")

    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    assert settings.event_plane_compactor_max_shards_per_run == 77
    assert settings.event_plane_backpressure_min_free_bytes == 12345
    assert settings.event_plane_backpressure_min_free_percent == 7
    assert settings.event_plane_backpressure_max_pending_shards == 222
