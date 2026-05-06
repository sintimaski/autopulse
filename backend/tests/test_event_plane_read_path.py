from __future__ import annotations

from pathlib import Path

from autopulse_backend.core.config import Settings
from autopulse_backend.services.event_plane_read_path import (
    select_dashboard_read_store_for_cutover,
)


def _settings(*, mode: str) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./x.db",
        event_store="duckdb",
        event_store_duckdb_path="./.autopulse/events.duckdb",
        event_plane_mode=mode,
        event_plane_snapshots_path="./.autopulse/events-duckdb",
    )


def test_cutover_selector_uses_legacy_store_when_toggle_disabled(monkeypatch) -> None:
    legacy = object()
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.get_duckdb_event_store",
        lambda: legacy,
    )

    selected = select_dashboard_read_store_for_cutover(
        use_snapshot_read=False,
        settings=_settings(mode="duckdb_log_shards"),
    )

    assert selected is legacy


def test_cutover_selector_uses_snapshot_store_when_enabled_and_snapshot_present(
    monkeypatch,
) -> None:
    legacy = object()
    snapshot = object()
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.get_duckdb_event_store",
        lambda: legacy,
    )
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.resolve_current_snapshot_duckdb_path",
        lambda _: Path("/tmp/snapshot/events.duckdb"),
    )
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.get_duckdb_read_store_for_path",
        lambda _: snapshot,
    )

    selected = select_dashboard_read_store_for_cutover(
        use_snapshot_read=True,
        settings=_settings(mode="duckdb_log_shards"),
    )

    assert selected is snapshot


def test_cutover_selector_falls_back_when_snapshot_missing(monkeypatch) -> None:
    legacy = object()
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.get_duckdb_event_store",
        lambda: legacy,
    )
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.resolve_current_snapshot_duckdb_path",
        lambda _: None,
    )

    selected = select_dashboard_read_store_for_cutover(
        use_snapshot_read=True,
        settings=_settings(mode="duckdb_log_shards"),
    )

    assert selected is legacy


def test_cutover_selector_ignores_snapshot_toggle_in_single_writer_mode(monkeypatch) -> None:
    legacy = object()
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.get_duckdb_event_store",
        lambda: legacy,
    )
    monkeypatch.setattr(
        "autopulse_backend.services.event_plane_read_path.resolve_current_snapshot_duckdb_path",
        lambda _: Path("/tmp/should-not-be-used.duckdb"),
    )

    selected = select_dashboard_read_store_for_cutover(
        use_snapshot_read=True,
        settings=_settings(mode="duckdb_single_writer"),
    )

    assert selected is legacy
