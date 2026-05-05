"""ASGI middleware that caps ingest request body bytes regardless of Content-Length.

Content-Length is optional in HTTP; clients using chunked or streaming uploads can
omit it entirely, bypassing a handler-level check. This middleware fully drains
the ingest request body into memory with an explicit cap and responds with 413
when the cap is exceeded, before the application code allocates anything bigger.
It only activates for ingest surfaces (``POST /ingest`` and OTLP trace
endpoints) so other paths keep their own semantics. Ingest payloads are already
small by design (capped batches of JSON events), so buffering the whole body is
acceptable and predictable.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from autopulse_backend.metrics import service_metrics

ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], ASGIReceive, ASGISend], Awaitable[None]]


logger = logging.getLogger(__name__)


def _is_ingest_request(scope: dict[str, Any]) -> bool:
    if scope.get("type") != "http":
        return False
    if (scope.get("method") or "").upper() != "POST":
        return False
    path = scope.get("path") or ""
    if not isinstance(path, str):
        return False
    ingest_paths = (
        "/ingest",
        "/otlp/v1/traces",
        "/ingest/otlp/v1/traces",
    )
    # Match bare API paths and mounted variants ending with known ingest surfaces.
    return any(path == candidate or path.endswith(candidate) for candidate in ingest_paths)


async def _send_413(send: ASGISend, max_bytes: int) -> None:
    service_metrics.increment("ingest.rejected.payload_too_large_stream")
    logger.warning(
        "ingest_rejected payload_too_large (stream cap)",
        extra={
            "event": "ingest_rejected",
            "reason": "payload_too_large_stream",
            "ingest_max_request_bytes": max_bytes,
        },
    )
    body = (
        b'{"detail":"Ingest payload exceeds max request size ('
        + str(max_bytes).encode("ascii")
        + b' bytes)."}'
    )
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class IngestBodySizeLimitMiddleware:
    """Enforce a byte cap on streamed request bodies for the ingest endpoint."""

    def __init__(self, app: ASGIApp, *, max_bytes_getter: Callable[[], int]) -> None:
        self._app = app
        self._max_bytes_getter = max_bytes_getter

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        if not _is_ingest_request(scope):
            await self._app(scope, receive, send)
            return

        max_bytes = max(1, int(self._max_bytes_getter()))
        buffered = bytearray()
        disconnected = False
        while True:
            message = await receive()
            msg_type = message.get("type")
            if msg_type == "http.disconnect":
                disconnected = True
                break
            if msg_type != "http.request":
                continue
            body: bytes = message.get("body") or b""
            if body:
                buffered.extend(body)
                if len(buffered) > max_bytes:
                    await _send_413(send, max_bytes)
                    # Drain any remaining chunks so the client closes cleanly.
                    more = message.get("more_body", False)
                    while more:
                        drained = await receive()
                        if drained.get("type") != "http.request":
                            break
                        more = drained.get("more_body", False)
                    return
            if not message.get("more_body", False):
                break

        if disconnected:
            # Client dropped mid-request; mirror behavior by letting the app
            # see an empty body and exit naturally.
            buffered = bytearray()

        replayed = False

        async def _replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": bytes(buffered),
                    "more_body": False,
                }
            # After the single replay, surface a disconnect so downstream awaits terminate.
            return {"type": "http.disconnect"}

        await self._app(scope, _replay_receive, send)
