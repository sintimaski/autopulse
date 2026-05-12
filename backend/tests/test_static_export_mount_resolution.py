from __future__ import annotations

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
