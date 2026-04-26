from __future__ import annotations

from fastapi import FastAPI

from autopulse_backend.ingest import router as ingest_router


def create_app() -> FastAPI:
    app = FastAPI(title="AutoPulse Backend")
    app.include_router(ingest_router)
    return app
