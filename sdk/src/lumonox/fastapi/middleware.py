"""FastAPI / Starlette adapter for the Lumonox SDK.

Everything in this module is Starlette-specific: route-template resolution
from ``request.scope``, FastAPI/Starlette startup/shutdown event-handler
registration, and the ``BaseHTTPMiddleware`` subclass that drives the
per-request capture. The bounded queue, transport, retries, scrubbing,
event-shape helpers, and infrastructure sampler all live under
``lumonox.core.*`` so a future Django / Flask / Litestar adapter can reuse
them without importing from ``lumonox.fastapi``. See ``sdk/docs/adapters.md``
for the adapter contract.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Awaitable, Callable
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from lumonox.core.config import _MonitorConfig, build_monitor_config
from lumonox.core.dispatcher import _EventDispatcher
from lumonox.core.events import (
    _build_infrastructure_widget_payload,
    _merge_release_git_into_event,
    _merge_widget_payloads,
    _stable_error_hash,
    _utc_now_iso,
)
from lumonox.core.paths import _normalize_mount_prefix, _path_is_ignored
from lumonox.core.runtime_context import reset_correlation_id, set_correlation_id
from lumonox.core.sampling import _should_sample_request
from lumonox.widgets import serialize_dashboard_widgets

logger = logging.getLogger("lumonox.monitor")


def _resolve_route_path(request: Request, *, mount_prefix: str | None) -> str:
    wire = request.url.path
    base = _normalize_mount_prefix(mount_prefix)
    if base and (wire == base or wire.startswith(f"{base}/")):
        return wire
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return template
    return wire


def _add_event_handler(app: Any, event: str, handler: Callable[[], Awaitable[None]]) -> bool:
    add_event_handler = getattr(app, "add_event_handler", None)
    if callable(add_event_handler):
        add_event_handler(event, handler)
        return True
    router = getattr(app, "router", None)
    router_add_event_handler = getattr(router, "add_event_handler", None)
    if callable(router_add_event_handler):
        router_add_event_handler(event, handler)
        return True
    return False


def _remove_event_handler(app: Any, event: str, handler: Callable[[], Awaitable[None]]) -> None:
    """Best-effort rollback for previously added startup/shutdown handlers."""
    handlers_attr = "on_startup" if event == "startup" else "on_shutdown"
    candidates = [
        getattr(app, handlers_attr, None),
        getattr(getattr(app, "router", None), handlers_attr, None),
    ]
    for handlers in candidates:
        if isinstance(handlers, list):
            while handler in handlers:
                handlers.remove(handler)


class _LumonoxMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, dispatcher: _EventDispatcher, config: _MonitorConfig) -> None:
        super().__init__(app)
        self._dispatcher = dispatcher
        self._config = config
        self._last_dashboard_widgets_attach_monotonic = 0.0

    def _attach_dashboard_widgets_if_due(self, common: dict[str, Any]) -> None:
        """Attach widget + infrastructure payloads at a bounded rate to avoid DB blowups."""
        cfg = self._config
        if not cfg.dashboard_widgets and cfg.infrastructure_sampler is None:
            return
        now = monotonic()
        interval = cfg.dashboard_widgets_attach_interval_s
        if (
            interval > 0
            and self._last_dashboard_widgets_attach_monotonic > 0.0
            and now - self._last_dashboard_widgets_attach_monotonic < interval
        ):
            return
        self._last_dashboard_widgets_attach_monotonic = now

        if cfg.dashboard_widgets:
            widget_payload = serialize_dashboard_widgets(list(cfg.dashboard_widgets))
            if widget_payload["definitions"] or widget_payload["points"]:
                common["dashboard_widgets"] = widget_payload

        if cfg.infrastructure_sampler is not None:
            infrastructure_metrics = cfg.infrastructure_sampler.sample()
            if infrastructure_metrics:
                common["infrastructure_metrics"] = infrastructure_metrics
                infra_widget_payload = _build_infrastructure_widget_payload(infrastructure_metrics)
                existing_widgets = common.get("dashboard_widgets")
                if (
                    isinstance(existing_widgets, dict)
                    and isinstance(existing_widgets.get("definitions"), list)
                    and isinstance(existing_widgets.get("points"), list)
                ):
                    common["dashboard_widgets"] = _merge_widget_payloads(
                        existing_widgets, infra_widget_payload
                    )
                else:
                    common["dashboard_widgets"] = infra_widget_payload

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started_at = perf_counter()
        header_rid = (request.headers.get("x-request-id") or "").strip()
        header_cid = (request.headers.get("x-correlation-id") or "").strip()
        correlation_id = (header_rid or header_cid or str(uuid4()))[:128]
        correlation_token = set_correlation_id(correlation_id)

        def _stamp_response(resp: Response) -> Response:
            if correlation_id:
                resp.headers.setdefault("X-Request-ID", correlation_id)
            return resp

        common: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "service_name": self._config.service_name,
            "environment": self._config.environment,
            "method": request.method,
            "request_id": correlation_id,
        }
        send_ok = getattr(
            self._dispatcher,
            "_send_enabled",
            bool(self._config.api_key and self._config.ingest_url),
        )
        if send_ok:
            self._attach_dashboard_widgets_if_due(common)
        if send_ok and self._config.capture_headers:
            common["headers"] = dict(request.headers.items())
        if send_ok and self._config.capture_query_params:
            common["query_params"] = dict(request.query_params.multi_items())
        _merge_release_git_into_event(self._config, common)
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                resolved_path = _resolve_route_path(request, mount_prefix=self._config.mount_prefix)
                if _path_is_ignored(resolved_path, self._config.ignore_path_prefixes):
                    raise
                latency_ms = (perf_counter() - started_at) * 1000
                stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                self._dispatcher.enqueue(
                    {
                        **common,
                        "path": resolved_path,
                        "type": "request",
                        "status_code": 500,
                        "latency_ms": round(latency_ms, 3),
                    }
                )
                self._dispatcher.enqueue(
                    {
                        **common,
                        "path": resolved_path,
                        "type": "error",
                        "status_code": 500,
                        "latency_ms": round(latency_ms, 3),
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "stack_trace": stack_trace,
                        "error_hash": _stable_error_hash(
                            type(exc).__name__,
                            str(exc),
                            stack_trace,
                            resolved_path,
                        ),
                    }
                )
                raise
            resolved_path = _resolve_route_path(request, mount_prefix=self._config.mount_prefix)
            if _path_is_ignored(resolved_path, self._config.ignore_path_prefixes):
                return _stamp_response(response)
            latency_ms = (perf_counter() - started_at) * 1000
            should_capture_request = response.status_code >= 500 or _should_sample_request(
                request_sample_rate=self._config.request_sample_rate,
                method=request.method,
                path=resolved_path,
                request_id=correlation_id,
            )
            if not should_capture_request:
                return _stamp_response(response)
            self._dispatcher.enqueue(
                {
                    **common,
                    "path": resolved_path,
                    "type": "request",
                    "status_code": response.status_code,
                    "latency_ms": round(latency_ms, 3),
                }
            )
            return _stamp_response(response)
        finally:
            reset_correlation_id(correlation_token)


def monitor(app: Any, **kwargs: Any) -> None:
    """Attach Lumonox monitoring to a FastAPI application.

    The SDK always fails silent by default: monitoring failures never block
    user requests.
    """
    if not all(hasattr(app, attr) for attr in ("state", "add_middleware")):
        return
    if getattr(app.state, "_lumonox_configured", False):
        return
    mode = str(kwargs.get("mode", "remote")).strip().lower()
    if mode == "embedded":
        logger.warning(
            "lumonox.monitor: mode='embedded' is no longer supported; "
            "run the backend separately and use remote ingest (LUMONOX_INGEST_URL + "
            "LUMONOX_API_KEY)."
        )
    config = build_monitor_config(**kwargs)
    dispatcher = _EventDispatcher(
        config,
        client=kwargs.get("http_client"),
        owns_client=kwargs.get("owns_http_client"),
    )
    if not dispatcher._send_enabled:
        logger.warning(
            "lumonox.monitor: remote ingest is disabled because LUMONOX_INGEST_URL and "
            "LUMONOX_API_KEY are not both set; middleware is attached but events will not "
            "be sent."
        )
    if not _add_event_handler(app, "startup", dispatcher.start):
        return
    startup_registered = True
    shutdown_registered = False
    if not _add_event_handler(app, "shutdown", dispatcher.stop):
        if startup_registered:
            _remove_event_handler(app, "startup", dispatcher.start)
        return
    shutdown_registered = True
    try:
        app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)
    except Exception:
        if shutdown_registered:
            _remove_event_handler(app, "shutdown", dispatcher.stop)
        if startup_registered:
            _remove_event_handler(app, "startup", dispatcher.start)
        return
    app.state._lumonox_config = config
    app.state._lumonox_dispatcher = dispatcher
    app.state._lumonox_configured = True
