from __future__ import annotations

from pathlib import Path

import pytest

from autopulse_backend.core.config import (
    normalize_alert_email_file_outbox_dir,
    normalize_event_store_duckdb_path,
    resolve_autopulse_data_root,
)


def test_normalize_relative_duckdb_path_anchors_under_data_root(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    out = normalize_event_store_duckdb_path(".autopulse/events.duckdb", data_root=root)
    assert out == str((root / ".autopulse" / "events.duckdb").resolve())


def test_normalize_default_relative_path(tmp_path: Path) -> None:
    out = normalize_event_store_duckdb_path("", data_root=tmp_path)
    assert out == str((tmp_path / ".autopulse" / "events.duckdb").resolve())


def test_normalize_absolute_path_ignores_data_root(tmp_path: Path) -> None:
    abs_path = tmp_path / "elsewhere" / "e.duckdb"
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    out = normalize_event_store_duckdb_path(str(abs_path), data_root=tmp_path / "ignored")
    assert out == str(abs_path.resolve())


def test_normalize_rejects_path_escape(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    with pytest.raises(ValueError, match="outside data root"):
        normalize_event_store_duckdb_path("../evil.duckdb", data_root=root)


def test_resolve_autopulse_data_root_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AUTOPULSE_PROJECT_ROOT", raising=False)
    monkeypatch.setenv("AUTOPULSE_DATA_DIR", str(tmp_path / "d"))
    assert resolve_autopulse_data_root() == (tmp_path / "d").resolve()


def test_resolve_autopulse_data_root_project_root_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AUTOPULSE_DATA_DIR", raising=False)
    monkeypatch.setenv("AUTOPULSE_PROJECT_ROOT", str(tmp_path / "p"))
    assert resolve_autopulse_data_root() == (tmp_path / "p").resolve()


def test_normalize_alert_email_file_outbox_dir_relative_under_root(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    out = normalize_alert_email_file_outbox_dir("./.autopulse/emails", data_root=root)
    assert out == str((root / ".autopulse" / "emails").resolve())


def test_normalize_alert_email_file_outbox_default(tmp_path: Path) -> None:
    out = normalize_alert_email_file_outbox_dir(None, data_root=tmp_path)
    assert out == str((tmp_path / ".autopulse" / "emails").resolve())


def test_normalize_alert_email_file_outbox_absolute_ignores_root(tmp_path: Path) -> None:
    abs_dir = tmp_path / "outbox"
    abs_dir.mkdir()
    out = normalize_alert_email_file_outbox_dir(str(abs_dir), data_root=tmp_path / "ignored")
    assert out == str(abs_dir.resolve())


def test_normalize_alert_email_file_outbox_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    with pytest.raises(ValueError, match="outside data root"):
        normalize_alert_email_file_outbox_dir("../evil-emails", data_root=root)
