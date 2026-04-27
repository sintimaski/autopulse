from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autopulse_backend.api.router import api_router
from autopulse_backend.api.routes.health import router as health_router
from autopulse_backend.core.config import get_settings
from autopulse_backend.lifespan import lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AutoPulse Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(api_router)
    if settings.dev_scenarios_enabled:
        from autopulse_backend.routes.dev_scenarios import router as dev_scenarios_router

        app.include_router(dev_scenarios_router)
    return app


def mount_on_app(host_app: Any, *, prefix: str = "/autopulse") -> FastAPI:
    """Mount the backend app under a host FastAPI application."""
    mounted_app = create_app()
    host_app.mount(prefix.rstrip("/") or "/", mounted_app)
    return mounted_app
