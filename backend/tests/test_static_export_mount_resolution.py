from __future__ import annotations

from pathlib import Path

import pytest


def test_resolve_dashboard_static_dir_ignores_invalid_env_and_finds_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a broken ``LUMONOX_FRONTEND_STATIC_DIR`` must not disable the mount entirely."""
    monkeypatch.setenv("LUMONOX_FRONTEND_STATIC_DIR", "/__lumonox_nonexistent_export_path__")
    from lumonox_backend.core.config import get_settings
    from lumonox_backend.dashboard.static_export_mount import _resolve_dashboard_static_dir

    got = _resolve_dashboard_static_dir(get_settings())
    if got is None:
        pytest.skip(
            "No ``frontend/out`` in workspace (run ``npm run build`` in ``frontend/`` first)."
        )
    assert (got / "index.html").is_file()


def test_bundled_dashboard_static_dir_resolves_at_package_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: the wheel ships the dashboard export at
    ``lumonox_backend/dashboard_static/`` — a sibling of the ``dashboard``
    subpackage. ``_bundled_dashboard_static_dir()`` must resolve there, not one
    level deeper under ``dashboard/``: that mismatch left ``pip install lumonox``
    runs with no dashboard UI unless ``LUMONOX_FRONTEND_STATIC_DIR`` was set.
    """
    from lumonox_backend.dashboard import static_export_mount as mod

    # Mirror the wheel layout: the module at <pkg>/dashboard/static_export_mount.py,
    # the bundled export at <pkg>/dashboard_static/.
    pkg_root = tmp_path / "lumonox_backend"
    (pkg_root / "dashboard").mkdir(parents=True)
    fake_module = pkg_root / "dashboard" / "static_export_mount.py"
    fake_module.write_text("", encoding="utf-8")
    bundled = pkg_root / "dashboard_static"
    bundled.mkdir()
    (bundled / "index.html").write_text("<!doctype html>\n", encoding="utf-8")

    monkeypatch.setattr(mod, "__file__", str(fake_module))
    assert mod._bundled_dashboard_static_dir() == bundled.resolve()

    # A stray copy nested under dashboard/ (the original buggy location) must not
    # change the answer — resolution always anchors at the package root.
    nested = pkg_root / "dashboard" / "dashboard_static"
    nested.mkdir()
    (nested / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
    assert mod._bundled_dashboard_static_dir() == bundled.resolve()
