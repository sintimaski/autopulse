from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from autopulse_backend.api.router import api_router
from autopulse_backend.api.routes.health import router as health_router
from autopulse_backend.core.config import get_settings
from autopulse_backend.dashboard.static_export_mount import maybe_mount_dashboard_static_export
from autopulse_backend.ingestion.body_size import IngestBodySizeLimitMiddleware
from autopulse_backend.lifespan import lifespan
from autopulse_backend.middleware.dashboard_origin import DashboardOriginEnforcementMiddleware
from autopulse_backend.middleware.gzip_request_body import GzipRequestBodyMiddleware


def create_app(*, for_submount: bool = False) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AutoPulse Backend", lifespan=lifespan)
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
    env = (settings.autopulse_env or "development").strip().lower()
    if settings.dev_scenarios_enabled and env != "production":
        from autopulse_backend.routes.dev_scenarios import router as dev_scenarios_router

        app.include_router(dev_scenarios_router)
    maybe_mount_dashboard_static_export(app, settings, for_submount=for_submount)
    return app


def mount_on_app(host_app: Any, *, prefix: str = "/autopulse") -> FastAPI:
    """Mount the backend app under a host FastAPI application."""
    mounted_app = create_app(for_submount=True)
    host_app.mount(prefix.rstrip("/") or "/", mounted_app)
    return mounted_app
