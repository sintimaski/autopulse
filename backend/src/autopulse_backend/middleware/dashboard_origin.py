"""Optional Origin checks for credentialed dashboard mutations (CSRF mitigation)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from autopulse_backend.core.config import get_settings

logger = logging.getLogger(__name__)

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _origin_matches_allowed(origin: str, allowed: tuple[str, ...]) -> bool:
    normalized = origin.strip()
    if not normalized:
        return False
    return any(normalized == allowed_origin for allowed_origin in allowed)


class DashboardOriginEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        if not settings.dashboard_enforce_origin_for_mutations:
            return await call_next(request)
        if request.method not in _UNSAFE_METHODS:
            return await call_next(request)
        path = request.url.path or ""
        if not path.startswith("/dashboard"):
            return await call_next(request)
        # Browser-driven OIDC callback is a GET; magic-link verify is POST from UI with Origin.
        origin = request.headers.get("origin")
        if origin is None or not origin.strip():
            referer = request.headers.get("referer")
            if referer:
                parsed = urlparse(referer)
                if parsed.scheme and parsed.netloc:
                    origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin is None or not origin.strip():
            logger.warning(
                "dashboard_origin_enforcement_missing_origin",
                extra={"path": path, "method": request.method},
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Origin header required for this request."},
            )
        if not _origin_matches_allowed(origin, settings.cors_allow_origins):
            logger.warning(
                "dashboard_origin_enforcement_rejected",
                extra={"path": path, "method": request.method, "origin": origin},
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Origin is not permitted for dashboard mutations."},
            )
        response: Response = await call_next(request)
        return response
