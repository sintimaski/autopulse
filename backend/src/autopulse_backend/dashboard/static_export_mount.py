"""Serve the Next static export from the API process (embedded-style dashboard)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from autopulse_backend.core.config import Settings

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


def _resolve_dashboard_static_dir(_settings: Settings) -> Path | None:
    env = os.getenv("AUTOPULSE_FRONTEND_STATIC_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir() and (p / "index.html").is_file():
            return p
        return None
    candidates = (
        Path.cwd() / "sdk" / "src" / "autopulse" / "ui",
        Path.cwd() / "frontend" / "out",
    )
    for raw in candidates:
        p = raw.resolve()
        if p.is_dir() and (p / "index.html").is_file():
            return p
    return None


def maybe_mount_dashboard_static_export(
    app: Any,
    settings: Settings,
    *,
    for_submount: bool = False,
) -> None:
    """Mount the Next static export when ``index.html`` exists (see bundle script in repo)."""
    if getattr(app.state, "_autopulse_dashboard_static_mounted", False):
        return
    static_dir = _resolve_dashboard_static_dir(settings)
    if static_dir is None:
        return
    mount_path = "/ui" if for_submount else "/autopulse/ui"
    app.mount(
        mount_path,
        _DashboardStaticExportFiles(directory=str(static_dir), html=True),
        name="autopulse-dashboard-static",
    )
    if not for_submount:

        @app.get("/", include_in_schema=False)  # type: ignore[untyped-decorator]
        async def _dashboard_root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/autopulse/ui/")

    app.state._autopulse_dashboard_static_mounted = True
    logger.info(
        "Mounted dashboard static export at %s from %s",
        mount_path,
        static_dir,
    )
