from __future__ import annotations

from pathlib import Path

import pytest

from autopulse_backend.core.config import (
    normalize_parquet_export_root,
    normalize_parquet_restore_root,
)


def test_normalize_parquet_export_root_relative_is_under_data_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    resolved = normalize_parquet_export_root("./.autopulse/parquet/events", data_root=root)
    path = Path(resolved)
    assert path.is_absolute()
    assert path.is_relative_to(root.resolve())


def test_normalize_parquet_export_root_rejects_path_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(ValueError, match="AUTOPULSE_PARQUET_EXPORT_ROOT"):
        normalize_parquet_export_root("../../outside-parquet", data_root=root)


def test_normalize_parquet_restore_root_rejects_path_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(ValueError, match="AUTOPULSE_PARQUET_OBJECT_STORAGE_RESTORE_ROOT"):
        normalize_parquet_restore_root("../../../etc/restore", data_root=root)
