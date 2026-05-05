"""Unit tests for the ASGI body-size middleware covering the no-Content-Length path.

``TestClient`` always sends a ``Content-Length`` header, so we exercise the ASGI
middleware directly with hand-crafted ``http.request`` messages to prove the cap
fires even when Content-Length is unavailable (e.g. chunked uploads).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from autopulse_backend.ingestion.body_size import IngestBodySizeLimitMiddleware


def _make_scope(*, path: str = "/ingest") -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
    }


async def _app_ok(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    body_parts: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        body_parts.append(message.get("body") or b"")
        if not message.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send(
        {
            "type": "http.response.body",
            "body": b'{"accepted":' + str(len(b"".join(body_parts))).encode() + b"}",
        }
    )


def _run_asgi(
    middleware: IngestBodySizeLimitMiddleware,
    scope: dict[str, Any],
    body_chunks: list[bytes],
) -> tuple[int, bytes]:
    async def runner() -> tuple[int, bytes]:
        messages = iter(
            [
                {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": index < len(body_chunks) - 1,
                }
                for index, chunk in enumerate(body_chunks)
            ]
        )

        async def receive() -> dict[str, Any]:
            return next(messages)

        sent: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        await middleware(scope, receive, send)
        status = next(msg["status"] for msg in sent if msg["type"] == "http.response.start")
        body = b"".join(msg.get("body", b"") for msg in sent if msg["type"] == "http.response.body")
        return status, body

    return asyncio.run(runner())


def test_middleware_rejects_oversize_body_without_content_length() -> None:
    middleware = IngestBodySizeLimitMiddleware(_app_ok, max_bytes_getter=lambda: 32)
    scope = _make_scope()
    scope["headers"] = [(b"content-type", b"application/json"), (b"transfer-encoding", b"chunked")]

    status, body = _run_asgi(
        middleware,
        scope,
        [b"x" * 16, b"y" * 16, b"z" * 16],
    )
    assert status == 413
    assert b"Ingest payload exceeds max request size" in body


def test_middleware_passes_through_small_body() -> None:
    middleware = IngestBodySizeLimitMiddleware(_app_ok, max_bytes_getter=lambda: 1024)
    scope = _make_scope()

    payload = json.dumps({"events": []}).encode()
    status, body = _run_asgi(middleware, scope, [payload])
    assert status == 200
    assert body == b'{"accepted":' + str(len(payload)).encode() + b"}"


def test_middleware_ignores_non_ingest_paths() -> None:
    middleware = IngestBodySizeLimitMiddleware(_app_ok, max_bytes_getter=lambda: 4)
    scope = _make_scope(path="/dashboard/auth/session")

    status, _ = _run_asgi(middleware, scope, [b"x" * 64])
    assert status == 200


def test_middleware_rejects_oversize_otlp_trace_body_without_content_length() -> None:
    middleware = IngestBodySizeLimitMiddleware(_app_ok, max_bytes_getter=lambda: 32)
    scope = _make_scope(path="/otlp/v1/traces")
    scope["headers"] = [(b"content-type", b"application/json"), (b"transfer-encoding", b"chunked")]

    status, body = _run_asgi(
        middleware,
        scope,
        [b"a" * 16, b"b" * 16, b"c" * 16],
    )
    assert status == 413
    assert b"Ingest payload exceeds max request size" in body
