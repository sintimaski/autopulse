from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from lumonox_backend.api.router import api_router
from lumonox_backend.api.routes.health import router as health_router
from lumonox_backend.core.config import get_settings
from lumonox_backend.dashboard.static_export_mount import maybe_mount_dashboard_static_export
from lumonox_backend.ingestion.body_size import IngestBodySizeLimitMiddleware
from lumonox_backend.lifespan import lifespan
from lumonox_backend.middleware.dashboard_origin import DashboardOriginEnforcementMiddleware
from lumonox_backend.middleware.gzip_request_body import GzipRequestBodyMiddleware


def create_app(*, for_submount: bool = False) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Lumonox Backend", lifespan=lifespan)
    app.add_middleware(
        IngestBodySizeLimitMiddleware,
        max_bytes_getter=lambda: get_settings().ingest_max_request_bytes,
    )
    app.add_middleware(DashboardOriginEnforcementMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Decode gzip-compressed request bodies (e.g. dashboard JSON) before ingest limits / routes.
    app.add_middleware(GzipRequestBodyMiddleware)
    # Compress JSON responses when the client accepts gzip (added last so it wraps the outer stack).
    app.add_middleware(GZipMiddleware, minimum_size=512, compresslevel=5)

    app.include_router(health_router)
    app.include_router(api_router)
    # Legacy path layout (embedded-era clients / stale bundles): mirror API under ``/lumonox``.
    app.include_router(api_router, prefix="/lumonox")
    env = (settings.lumonox_env or "development").strip().lower()
    if settings.dev_scenarios_enabled and env != "production":
        from lumonox_backend.routes.dev_scenarios import router as dev_scenarios_router

        app.include_router(dev_scenarios_router)

    @app.get("/favicon.ico", include_in_schema=False)
    async def _favicon_placeholder() -> Response:
        # Prevent noisy 404 logs in local/dev when no favicon asset is packaged.
        return Response(status_code=204)

    maybe_mount_dashboard_static_export(app, settings, for_submount=for_submount)
    return app


def mount_on_app(host_app: Any, *, prefix: str = "/lumonox") -> FastAPI:
    """Mount the backend app under a host FastAPI application."""
    mounted_app = create_app(for_submount=True)
    host_app.mount(prefix.rstrip("/") or "/", mounted_app)
    return mounted_app
