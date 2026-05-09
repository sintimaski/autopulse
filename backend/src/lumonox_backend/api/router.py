from __future__ import annotations

from fastapi import APIRouter

from lumonox_backend.dashboard import router as dashboard_router
from lumonox_backend.routes.ingest import router as ingest_router
from lumonox_backend.routes.rum import router as rum_router

api_router = APIRouter()
api_router.include_router(ingest_router)
api_router.include_router(rum_router)
api_router.include_router(dashboard_router)
