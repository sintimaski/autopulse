"""Django async middleware for the Lumonox SDK.

Mirrors ``lumonox.fastapi.middleware`` semantically but speaks Django's
request/response shapes. The bounded queue, transport, scrubbing,
infrastructure sampler, event-shape helpers, and config builder are all
reused from ``lumonox.core.*`` so a new framework adapter is purely the
glue you see in this file.

Hard contracts (mirrors ``.cursor/rules/lumonox-engineering.mdc``):

- Never break the host app: if ``monitor()`` was not called or any internal
  check fails, the middleware passes the request through untouched.
- Hot path is async / non-blocking: events go onto the bounded
  ``asyncio.Queue`` inside ``_EventDispatcher`` and the dispatcher's
  background task does the gzip-batched POSTs.
- Scrub before send: ``_EventDispatcher.enqueue`` calls ``_scrub_value``
  with the configured scrub keys; we never bypass it.
- Re-raise on exception: the SDK captures the event and then re-raises the
  original exception so Django's error pipeline still runs.
"""

from __future__ import annotations

import contextlib
import time
import traceback
import uuid
from typing import Any

from lumonox.core.config import _MonitorConfig, build_monitor_config
from lumonox.core.dispatcher import _EventDispatcher
from lumonox.core.events import (
    _build_infrastructure_widget_payload,
    _merge_release_git_into_event,
    _merge_widget_payloads,
    _stable_error_hash,
    _utc_now_iso,
)
from lumonox.core.paths import _path_is_ignored
from lumonox.core.runtime_context import reset_correlation_id, set_correlation_id
from lumonox.core.sampling import _should_sample_request
from lumonox.widgets import serialize_dashboard_widgets

# Django's exception middleware catches view exceptions BEFORE outer middleware
# sees them and converts them into 500 responses. To still emit a rich error
# event we hook ``django.core.signals.got_request_exception``: the handler
# attaches the exception to ``request._lumonox_exception`` (the request object
# travels through the sync_to_async boundary intact, contextvars do not), and
# the middleware reads that attribute when it sees a 500 come back. This is
# the same pattern django-debug-toolbar and sentry-django use.
_REQUEST_EXCEPTION_ATTR = "_lumonox_exception"

_DJANGO_INSTALL_HINT = (
    "lumonox.django requires Django. Install via "
    '`pip install "lumonox-sdk[django]"` or `pip install django`.'
)


def _ensure_django() -> None:
    """Raise a clear ImportError if Django is not available."""
    try:
        import django  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only when Django absent
        raise ImportError(_DJANGO_INSTALL_HINT) from exc


class _Runtime:
    """Process-level slot for the dispatcher + config the middleware reads.

    Django does not give middleware a per-app state object (FastAPI's
    ``app.state``), so we keep one ``_MonitorConfig`` + ``_EventDispatcher``
    per process. ``monitor()`` writes this slot; the middleware reads it on
    every request. Initialized lazily so the class is import-safe even
    before ``monitor()`` runs.
    """

    config: _MonitorConfig | None = None
    dispatcher: _EventDispatcher | None = None
    _last_widgets_attach_monotonic: float = 0.0


def monitor(**kwargs: Any) -> _EventDispatcher:
    """Build the Lumonox dispatcher + config for the Django adapter.

    Call once at process startup (e.g. inside your ``asgi.py`` next to
    ``get_asgi_application()``, or your ``AppConfig.ready()``). Add
    ``"lumonox.django.middleware.LumonoxMiddleware"`` to ``MIDDLEWARE`` in
    your settings.

    Returns the dispatcher. If you used ``wrap_asgi(...)`` to wrap your
    ASGI app, lifespan startup/shutdown will run ``await dispatcher.start()``
    / ``await dispatcher.stop()`` automatically. Otherwise you must drive
    those yourself (Django's classic WSGI does not expose lifespan).
    """
    _ensure_django()
    config = build_monitor_config(**kwargs)
    dispatcher = _EventDispatcher(
        config,
        client=kwargs.get("http_client"),
        owns_client=kwargs.get("owns_http_client"),
    )
    _Runtime.config = config
    _Runtime.dispatcher = dispatcher
    _install_exception_signal_once()
    return dispatcher


_signal_installed = False


def _exception_signal_handler(sender: Any, request: Any = None, **_kwargs: Any) -> None:
    """Module-level signal receiver so Django's weak-ref registry keeps it alive.

    A nested-function receiver would be eligible for GC after
    ``_install_exception_signal_once`` returns; the connect() call would
    appear to succeed but the handler would silently disappear on the next
    Python GC pass. Module-level keeps the reference strong.
    """
    import sys

    exc_info = sys.exc_info()
    if request is None or not exc_info or exc_info[1] is None:
        return
    try:
        setattr(request, _REQUEST_EXCEPTION_ATTR, exc_info[1])
    except Exception:  # pragma: no cover - host-app safety
        return


def _install_exception_signal_once() -> None:
    """Connect to Django's ``got_request_exception`` so we can attach exception details to 500s.

    Idempotent — the signal is installed once per process.
    """
    global _signal_installed
    if _signal_installed:
        return
    try:
        from django.core.signals import got_request_exception
    except Exception:  # pragma: no cover - host-app safety
        return
    got_request_exception.connect(
        _exception_signal_handler,
        dispatch_uid="lumonox.django.middleware",
    )
    _signal_installed = True


def _resolve_django_route_path(request: Any) -> str:
    """Best-effort route template from Django's resolver_match; falls back to ``request.path``."""
    resolver_match = getattr(request, "resolver_match", None)
    template = getattr(resolver_match, "route", None) if resolver_match is not None else None
    if isinstance(template, str) and template:
        # Django route templates often lack a leading slash; align with FastAPI's
        # "/users/{id}" shape so the dashboard groups them the same way.
        return template if template.startswith("/") else f"/{template}"
    raw_path = getattr(request, "path", "") or "/"
    return raw_path


def _stamp_response_header(response: Any, correlation_id: str) -> None:
    """Set X-Request-ID on the response if not already present (silent on failure)."""
    if not correlation_id:
        return
    try:
        headers = getattr(response, "headers", None)
        if headers is None or "X-Request-ID" not in headers:
            response["X-Request-ID"] = correlation_id
    except Exception:  # pragma: no cover - host-app safety
        return


def _attach_widgets_if_due(common: dict[str, Any], config: _MonitorConfig) -> None:
    """Throttled attach of widget + infrastructure payloads (mirrors the FastAPI path)."""
    if not config.dashboard_widgets and config.infrastructure_sampler is None:
        return
    now = time.monotonic()
    interval = config.dashboard_widgets_attach_interval_s
    if (
        interval > 0
        and _Runtime._last_widgets_attach_monotonic > 0.0
        and now - _Runtime._last_widgets_attach_monotonic < interval
    ):
        return
    _Runtime._last_widgets_attach_monotonic = now
    if config.dashboard_widgets:
        widget_payload = serialize_dashboard_widgets(list(config.dashboard_widgets))
        if widget_payload["definitions"] or widget_payload["points"]:
            common["dashboard_widgets"] = widget_payload
    if config.infrastructure_sampler is not None:
        infrastructure_metrics = config.infrastructure_sampler.sample()
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


class LumonoxMiddleware:
    """Django async middleware. Add to ``MIDDLEWARE`` in your settings.

    The middleware is a passthrough until ``monitor()`` has been called. On
    every request after that:

    1. Extract / synthesize a correlation id (preferring incoming
       ``X-Request-ID`` or ``X-Correlation-ID``) and set it on the request
       context so background jobs scheduled within the request inherit it.
    2. Call ``self.get_response(request)``; on exception capture a
       request + error event and re-raise.
    3. On success enqueue a request event (unless the path is ignored or
       sampled out) and stamp ``X-Request-ID`` on the response.
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    async def __call__(self, request: Any) -> Any:
        config = _Runtime.config
        dispatcher = _Runtime.dispatcher
        if config is None or dispatcher is None:
            # ``monitor()`` was not called — be invisible to the host app.
            return await self.get_response(request)

        started_at = time.perf_counter()
        headers = getattr(request, "headers", {})
        header_rid = (headers.get("x-request-id") or headers.get("X-Request-ID") or "").strip()
        header_cid = (
            headers.get("x-correlation-id") or headers.get("X-Correlation-ID") or ""
        ).strip()
        correlation_id = (header_rid or header_cid or uuid.uuid4().hex)[:128]
        correlation_token = set_correlation_id(correlation_id)

        common: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "service_name": config.service_name,
            "environment": config.environment,
            "method": request.method,
            "request_id": correlation_id,
        }
        send_ok = getattr(
            dispatcher,
            "_send_enabled",
            bool(config.api_key and config.ingest_url),
        )
        if send_ok:
            _attach_widgets_if_due(common, config)
        if send_ok and config.capture_headers:
            with contextlib.suppress(Exception):
                common["headers"] = dict(headers.items())
        if send_ok and config.capture_query_params:
            with contextlib.suppress(Exception):
                common["query_params"] = dict(request.GET.items())
        _merge_release_git_into_event(config, common)

        try:
            try:
                response = await self.get_response(request)
            except Exception as exc:
                resolved_path = _resolve_django_route_path(request)
                if _path_is_ignored(resolved_path, config.ignore_path_prefixes):
                    raise
                latency_ms = (time.perf_counter() - started_at) * 1000
                stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                dispatcher.enqueue(
                    {
                        **common,
                        "path": resolved_path,
                        "type": "request",
                        "status_code": 500,
                        "latency_ms": round(latency_ms, 3),
                    }
                )
                dispatcher.enqueue(
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

            resolved_path = _resolve_django_route_path(request)
            if _path_is_ignored(resolved_path, config.ignore_path_prefixes):
                _stamp_response_header(response, correlation_id)
                return response
            latency_ms = (time.perf_counter() - started_at) * 1000
            should_capture_request = response.status_code >= 500 or _should_sample_request(
                request_sample_rate=config.request_sample_rate,
                method=request.method,
                path=resolved_path,
                request_id=correlation_id,
            )
            if not should_capture_request:
                _stamp_response_header(response, correlation_id)
                return response
            dispatcher.enqueue(
                {
                    **common,
                    "path": resolved_path,
                    "type": "request",
                    "status_code": response.status_code,
                    "latency_ms": round(latency_ms, 3),
                }
            )
            # Django catches view exceptions in its own exception middleware and
            # returns a 500 response, so by the time we get here a ``type=error``
            # event has to be assembled from the ``got_request_exception`` signal
            # we caught earlier — not from a Python exception in this frame.
            if response.status_code >= 500:
                pending_exc = getattr(request, _REQUEST_EXCEPTION_ATTR, None)
                if pending_exc is not None:
                    stack_trace = "".join(
                        traceback.format_exception(
                            type(pending_exc), pending_exc, pending_exc.__traceback__
                        )
                    )
                    dispatcher.enqueue(
                        {
                            **common,
                            "path": resolved_path,
                            "type": "error",
                            "status_code": response.status_code,
                            "latency_ms": round(latency_ms, 3),
                            "exception_type": type(pending_exc).__name__,
                            "exception_message": str(pending_exc),
                            "stack_trace": stack_trace,
                            "error_hash": _stable_error_hash(
                                type(pending_exc).__name__,
                                str(pending_exc),
                                stack_trace,
                                resolved_path,
                            ),
                        }
                    )
            _stamp_response_header(response, correlation_id)
            return response
        finally:
            reset_correlation_id(correlation_token)


def wrap_asgi(asgi_app: Any) -> Any:
    """Wrap a Django ASGI app so lifespan startup/shutdown drives the dispatcher.

    This is the one-line ergonomic option: ``monitor()`` once, ``wrap_asgi``
    your ASGI app, done. Without it you would need to call
    ``await dispatcher.start()`` / ``await dispatcher.stop()`` yourself.
    """

    async def _wrapped(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "lifespan":
            await _lifespan(scope, receive, send, asgi_app)
            return
        await asgi_app(scope, receive, send)

    return _wrapped


async def _lifespan(scope: dict[str, Any], receive: Any, send: Any, asgi_app: Any) -> None:
    """Run startup/shutdown on our dispatcher, then forward to the inner app.

    Most Django ASGI apps do not implement the lifespan protocol; we handle
    it here even if the inner app does not. If the inner app does implement
    lifespan we still want it to run, so we forward each message after our
    own start/stop has completed.
    """
    inner_handles_lifespan = True
    while True:
        message = await receive()
        message_type = message.get("type")
        if message_type == "lifespan.startup":
            try:
                dispatcher = _Runtime.dispatcher
                if dispatcher is not None:
                    await dispatcher.start()
            except Exception as exc:  # pragma: no cover - host-app safety
                await send({"type": "lifespan.startup.failed", "message": str(exc)})
                return
            if inner_handles_lifespan:
                try:
                    await _forward_lifespan_message(asgi_app, scope, message)
                except Exception:
                    inner_handles_lifespan = False
            await send({"type": "lifespan.startup.complete"})
        elif message_type == "lifespan.shutdown":
            try:
                dispatcher = _Runtime.dispatcher
                if dispatcher is not None:
                    await dispatcher.stop()
            except Exception as exc:  # pragma: no cover - host-app safety
                await send({"type": "lifespan.shutdown.failed", "message": str(exc)})
                return
            if inner_handles_lifespan:
                with contextlib.suppress(Exception):
                    await _forward_lifespan_message(asgi_app, scope, message)
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _forward_lifespan_message(
    asgi_app: Any, scope: dict[str, Any], message: dict[str, Any]
) -> None:
    """Forward a single lifespan message to the inner app, swallowing its replies.

    Best-effort: if the inner app does not implement lifespan it will raise,
    which we swallow at the call site. The outer wrap always sends the
    canonical ``startup.complete`` / ``shutdown.complete`` reply itself so the
    server never hangs waiting for one.
    """

    async def _noop_send(_msg: dict[str, Any]) -> None:
        return

    sent_once = {"done": False}

    async def _single_message_receive() -> dict[str, Any]:
        if sent_once["done"]:
            # ASGI servers usually expect another message after startup/shutdown;
            # return a no-op disconnect-equivalent so the inner app exits cleanly.
            return {"type": "lifespan.shutdown"}
        sent_once["done"] = True
        return message

    await asgi_app(scope, _single_message_receive, _noop_send)
