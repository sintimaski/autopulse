from __future__ import annotations

from fastapi import APIRouter

from lumonox_backend.dashboard.routes import (
    alert_routes,
    auth_routes,
    bookmark_routes,
    diagnosis,
    error_groups,
    log_query_routes,
    oidc_routes,
    organization_routes,
    overview,
    query_bundle,
    query_explorer,
    requests_routes,
    traces,
    ui_settings,
    websockets,
    widgets,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
router.include_router(auth_routes.router)
router.include_router(oidc_routes.router)
router.include_router(websockets.router)
router.include_router(overview.router)
router.include_router(diagnosis.router)
router.include_router(requests_routes.router)
router.include_router(error_groups.router)
router.include_router(alert_routes.router)
router.include_router(ui_settings.router)
router.include_router(bookmark_routes.router)
router.include_router(log_query_routes.router)
router.include_router(query_explorer.router)
router.include_router(traces.router)
router.include_router(organization_routes.router)
router.include_router(widgets.router)
router.include_router(query_bundle.router)

__all__ = ["router"]
