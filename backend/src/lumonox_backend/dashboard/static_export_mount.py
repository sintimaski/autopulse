"""Serve the Next static export from the API process (dashboard UI mount)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from lumonox_backend.core.config import Settings

logger = logging.getLogger(__name__)

_DASHBOARD_UI_ASSET_SUFFIXES: frozenset[str] = frozenset(
    {
        ".css",
        ".eot",
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".map",
        ".mjs",
        ".png",
        ".svg",
        ".ttf",
        ".txt",
        ".webp",
        ".woff",
        ".woff2",
    }
)


def _dashboard_ui_path_looks_like_static_asset(path: str) -> bool:
    tail = path.rstrip("/").rsplit("/", 1)[-1].lower()
    if "." not in tail:
        return False
    return any(tail.endswith(suffix) for suffix in _DASHBOARD_UI_ASSET_SUFFIXES)


class _DashboardStaticExportFiles(StaticFiles):
    """Next static export; fall back to ``index.html`` for client-side routes."""

    async def get_response(self, path: str, scope: Scope) -> Any:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or not self.html:
                raise
            if _dashboard_ui_path_looks_like_static_asset(path):
                raise
            return await super().get_response("index.html", scope)


def _bundled_dashboard_static_dir() -> Path | None:
    """Bundled dashboard export shipped inside the ``lumonox_backend`` wheel.

    The wheel places the Next export at ``lumonox_backend/dashboard_static/`` — a
    sibling of this ``dashboard`` subpackage, *not* nested under it (see the sdist
    ``force-include`` in ``backend/pyproject.toml`` and the publish workflow's
    wheel-contents check). ``parents[1]`` is the ``lumonox_backend`` package root;
    ``__file__`` lives at ``lumonox_backend/dashboard/static_export_mount.py``.
    """
    bundled = Path(__file__).resolve().parents[1] / "dashboard_static"
    if bundled.is_dir() and (bundled / "index.html").is_file():
        return bundled
    return None


def _find_workspace_frontend_out_dir() -> Path | None:
    """Locate ``frontend/out`` for monorepo / editable installs.

    - Walk ``cwd`` and its parents (covers ``uvicorn`` started from ``backend/``).
    - Walk parents of this module (covers misleading ``cwd`` when the package lives under the repo).
    """
    seen: set[Path] = set()
    ordered: list[Path] = [
        Path.cwd().resolve(),
        *Path.cwd().resolve().parents,
        *Path(__file__).resolve().parents,
    ]
    for base in ordered:
        b = base.resolve()
        if b in seen:
            continue
        seen.add(b)
        candidate = (b / "frontend" / "out").resolve()
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


def _resolve_dashboard_static_dir(_settings: Settings) -> Path | None:
    env = os.getenv("LUMONOX_FRONTEND_STATIC_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir() and (p / "index.html").is_file():
            return p
        logger.warning(
            "LUMONOX_FRONTEND_STATIC_DIR is set but does not point at a Next export root "
            "(expected index.html). Ignoring and searching for frontend/out. path=%s",
            p,
        )
    workspace = _find_workspace_frontend_out_dir()
    if workspace is not None:
        return workspace
    bundled = _bundled_dashboard_static_dir()
    if bundled is not None:
        return bundled
    return None


def maybe_mount_dashboard_static_export(
    app: Any,
    settings: Settings,
    *,
    for_submount: bool = False,
) -> None:
    """Mount the Next static export when ``index.html`` exists (see bundle script in repo)."""
    if getattr(app.state, "_lumonox_dashboard_static_mounted", False):
        return
    static_dir = _resolve_dashboard_static_dir(settings)
    if static_dir is None:
        return
    mount_path = "/ui" if for_submount else "/lumonox/ui"
    app.mount(
        mount_path,
        _DashboardStaticExportFiles(directory=str(static_dir), html=True),
        name="lumonox-dashboard-static",
    )
    if not for_submount:

        @app.get("/", include_in_schema=False)  # type: ignore[untyped-decorator]
        async def _dashboard_root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/lumonox/ui/")

    app.state._lumonox_dashboard_static_mounted = True
    logger.info(
        "Mounted dashboard static export at %s from %s",
        mount_path,
        static_dir,
    )
