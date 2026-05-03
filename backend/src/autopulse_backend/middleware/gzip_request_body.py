"""ASGI middleware: decode ``Content-Encoding: gzip`` request bodies before routing.

Downstream handlers see the decompressed bytes as a normal JSON body. Wire limits
and decompressed caps reduce zip-bomb risk. Non-gzip requests pass through unchanged.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], ASGIReceive, ASGISend], Awaitable[None]]

# Dashboard query payloads are JSON; allow generous headroom for compressed wire size.
_MAX_WIRE_GZIP_BYTES = 8 * 1024 * 1024
_MAX_DECOMPRESSED_BYTES = 32 * 1024 * 1024


def _header_value(scope: dict[str, Any], name: bytes) -> bytes | None:
    for key, val in scope.get("headers") or []:
        if not isinstance(key, bytes | bytearray) or not isinstance(val, bytes | bytearray):
            continue
        if bytes(key).lower() == name:
            return bytes(val)
    return None


def _first_content_encoding_token(raw: bytes) -> bytes:
    return raw.split(b",", 1)[0].strip().lower()


def _scope_with_decoded_body(scope: dict[str, Any], decompressed: bytes) -> dict[str, Any]:
    new_headers: list[tuple[bytes, bytes]] = []
    content_length_set = False
    for key, val in scope.get("headers") or []:
        if not isinstance(key, bytes | bytearray) or not isinstance(val, bytes | bytearray):
            continue
        kb = bytes(key).lower()
        vb = bytes(val)
        if kb == b"content-encoding":
            continue
        if kb == b"content-length":
            new_headers.append((b"content-length", str(len(decompressed)).encode("ascii")))
            content_length_set = True
            continue
        new_headers.append((bytes(key), vb))
    if not content_length_set:
        new_headers.append((b"content-length", str(len(decompressed)).encode("ascii")))
    new_scope = dict(scope)
    new_scope["headers"] = new_headers
    return new_scope


async def _send_json_error(send: ASGISend, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class GzipRequestBodyMiddleware:
    """If ``Content-Encoding`` starts with ``gzip``, buffer, decompress, replay body."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: dict[str, Any], receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        method = (scope.get("method") or "").upper()
        if method not in {"POST", "PUT", "PATCH"}:
            await self._app(scope, receive, send)
            return

        raw_enc = _header_value(scope, b"content-encoding")
        if raw_enc is None or _first_content_encoding_token(raw_enc) != b"gzip":
            await self._app(scope, receive, send)
            return

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
            chunk: bytes = message.get("body") or b""
            if chunk:
                buffered.extend(chunk)
                if len(buffered) > _MAX_WIRE_GZIP_BYTES:
                    logger.warning(
                        "gzip_request_rejected compressed_too_large",
                        extra={"event": "gzip_request_rejected", "reason": "compressed_too_large"},
                    )
                    await _send_json_error(
                        send,
                        413,
                        "Compressed request body exceeds maximum size.",
                    )
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
            buffered = bytearray()

        if not buffered:
            await _send_json_error(send, 400, "Empty gzip request body.")
            return

        try:
            with gzip.GzipFile(fileobj=io.BytesIO(bytes(buffered)), mode="rb") as gz:
                decompressed = gz.read(_MAX_DECOMPRESSED_BYTES + 1)
        except (OSError, EOFError, gzip.BadGzipFile) as exc:
            logger.info("gzip_request_rejected invalid_gzip: %s", exc)
            await _send_json_error(send, 400, "Invalid gzip request body.")
            return

        if len(decompressed) > _MAX_DECOMPRESSED_BYTES:
            logger.warning(
                "gzip_request_rejected decompressed_too_large",
                extra={"event": "gzip_request_rejected", "reason": "decompressed_too_large"},
            )
            await _send_json_error(send, 413, "Decompressed request body exceeds maximum size.")
            return

        new_scope = _scope_with_decoded_body(scope, decompressed)
        replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": decompressed, "more_body": False}
            return {"type": "http.disconnect"}

        await self._app(new_scope, replay_receive, send)
