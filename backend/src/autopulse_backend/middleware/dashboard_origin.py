"""Optional Origin header checks for credentialed dashboard mutations (CSRF mitigation)."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from autopulse_backend.core.config import get_settings

logger = logging.getLogger(__name__)

_UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _origin_allowed(origin: str, allowed: tuple[str, ...]) -> bool:
    o = origin.strip()
    if not o:
        return False
    return any(o == a for a in allowed)


class DashboardOriginEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if not settings.dashboard_enforce_origin_for_mutations:
            return await call_next(request)
        if request.method not in _UNSAFE:
            return await call_next(request)
        path = request.url.path or ""
        if not path.startswith("/dashboard"):
            return await call_next(request)
        origin_header = request.headers.get("origin")
        resolved_origin = (origin_header or "").strip()
        if not resolved_origin:
            referer = request.headers.get("referer")
            if referer:
                parsed = urlparse(referer)
                if parsed.scheme and parsed.netloc:
                    resolved_origin = f"{parsed.scheme}://{parsed.netloc}"
        if not resolved_origin:
            logger.warning(
                "dashboard_origin_missing",
                extra={"path": path, "method": request.method},
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Origin header required for this request."},
            )
        if not _origin_allowed(resolved_origin, settings.cors_allow_origins):
            logger.warning(
                "dashboard_origin_rejected",
                extra={"path": path, "method": request.method, "origin": resolved_origin},
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Origin is not permitted for dashboard mutations."},
            )
        response: Response = await call_next(request)
        return response
