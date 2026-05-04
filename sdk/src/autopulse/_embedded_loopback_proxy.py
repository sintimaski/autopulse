"""ASGI reverse proxy: host ``/autopulse`` → loopback AutoPulse server (HTTP + WebSocket)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

import httpx

_LOG = logging.getLogger(__name__)

_HOP_BY_HOP_REQUEST = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)
_HOP_BY_HOP_RESPONSE = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        # We stream decoded bodies from ``httpx.Response.aiter_bytes()``; drop encoding metadata.
        "content-encoding",
        "content-length",
    }
)

# ``websockets.connect`` already emits a fresh handshake (key, version, extensions, subprotocol).
# Forwarding the browser's ``Sec-WebSocket-*`` headers merges duplicates (Headers.update appends),
# which makes Starlette/Uvicorn reject the upgrade with HTTP 400 ("multiple values").
_WS_CLIENT_REGENERATES = frozenset(
    {
        "sec-websocket-key",
        "sec-websocket-version",
        "sec-websocket-extensions",
        "sec-websocket-protocol",
    }
)


def _decode_header_list(scope_headers: list[tuple[bytes, bytes]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for raw_k, raw_v in scope_headers:
        try:
            k = raw_k.decode("latin-1")
            v = raw_v.decode("latin-1")
        except UnicodeDecodeError:
            continue
        if k.lower() in _HOP_BY_HOP_REQUEST:
            continue
        out.append((k, v))
    return out


def _filter_response_headers(items: httpx.Headers) -> list[tuple[bytes, bytes]]:
    out: list[tuple[bytes, bytes]] = []
    for k, v in items.multi_items():
        if k.lower() in _HOP_BY_HOP_RESPONSE:
            continue
        out.append((k.encode("latin-1"), v.encode("latin-1")))
    return out


def _websocket_upstream_additional_headers(
    scope_headers: list[tuple[bytes, bytes]], *, upstream_host_header: str
) -> tuple[list[tuple[str, str]], str | None]:
    """Build ``websockets.connect`` handshake inputs from the incoming ASGI scope.

    Returns ``(additional_headers, origin)`` — pass ``origin`` as the connect
    kwarg (not as a header) so it cannot duplicate ``Origin`` from
    ``additional_headers``. ``Headers.update`` appends duplicate names, which
    makes the upstream ``websockets`` server reject the handshake with HTTP 400
    (e.g. multiple ``Origin`` or ``Host``).

    Non-cookie headers are deduplicated case-insensitively (last value wins).
    Multiple ``cookie`` lines are merged into one ``Cookie`` value.
    """
    decoded = _decode_header_list(list(scope_headers or []))
    filtered = [(k, v) for k, v in decoded if k.lower() not in _WS_CLIENT_REGENERATES]

    origin: str | None = None
    cookies: list[str] = []
    other_order: list[str] = []
    other_last: dict[str, tuple[str, str]] = {}

    for k, v in filtered:
        lk = k.lower()
        if lk == "origin":
            origin = v
            continue
        if lk == "cookie":
            cookies.append(v)
            continue
        if lk not in other_last:
            other_order.append(lk)
        other_last[lk] = (k, v)

    out: list[tuple[str, str]] = [other_last[lk] for lk in other_order]
    if cookies:
        out.append(("Cookie", "; ".join(cookies)))
    out.append(("Host", upstream_host_header))
    return out, origin


class AutopulseLoopbackMountProxy:
    """Forward ASGI traffic to the loopback AutoPulse process.

    Starlette ``Mount`` forwards the **full** wire path (e.g. ``/autopulse/ingest``) to the
    sub-application scope, so the upstream URL is ``http://127.0.0.1:<port>`` + that path.
    """

    __slots__ = ("_http_origin", "_ws_origin", "_upstream_host_header", "_client")

    def __init__(self, *, loopback_port: int) -> None:
        self._http_origin = f"http://127.0.0.1:{loopback_port}"
        self._ws_origin = f"ws://127.0.0.1:{loopback_port}"
        self._upstream_host_header = f"127.0.0.1:{loopback_port}"
        self._client: httpx.AsyncClient | None = None

    @staticmethod
    def _scope_path(scope: dict[str, Any]) -> str:
        raw = scope.get("path") or "/"
        return raw if raw.startswith("/") else f"/{raw}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            await self._proxy_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._proxy_websocket(scope, receive, send)
        else:
            await send(
                {
                    "type": "http.response.start",
                    "status": 501,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"Unsupported scope type",
                    "more_body": False,
                }
            )

    async def _proxy_http(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        path = self._scope_path(scope)
        qs = scope.get("query_string", b"")
        url = f"{self._http_origin}{path}"
        if qs:
            url = f"{url}?{qs.decode('latin-1')}"
        method = scope.get("method", "GET").upper()
        headers = _decode_header_list(list(scope.get("headers") or []))
        headers.append(("Host", self._upstream_host_header))

        body = b""
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                continue
            body += message.get("body") or b""
            more = bool(message.get("more_body"))

        client = await self._get_client()
        try:
            upstream = await client.request(method, url, headers=headers, content=body)
        except httpx.RequestError as exc:
            _LOG.warning("autopulse_embedded_proxy_http_error url=%s err=%s", url, exc)
            await send(
                {
                    "type": "http.response.start",
                    "status": 502,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"AutoPulse embedded proxy could not reach the loopback server.",
                    "more_body": False,
                }
            )
            return

        out_headers = _filter_response_headers(upstream.headers)
        await send(
            {"type": "http.response.start", "status": upstream.status_code, "headers": out_headers}
        )
        async for chunk in upstream.aiter_bytes():
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def _proxy_websocket(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        from websockets.asyncio.client import connect as ws_connect
        from websockets.exceptions import ConnectionClosed

        path = self._scope_path(scope)
        qs = scope.get("query_string", b"")
        uri = f"{self._ws_origin}{path}"
        if qs:
            uri = f"{uri}?{qs.decode('latin-1')}"

        headers, ws_origin = _websocket_upstream_additional_headers(
            list(scope.get("headers") or []),
            upstream_host_header=self._upstream_host_header,
        )

        first = await receive()
        if first.get("type") != "websocket.connect":
            return

        try:
            connect_kw: dict[str, Any] = {}
            if ws_origin is not None:
                connect_kw["origin"] = ws_origin
            upstream = await ws_connect(uri, additional_headers=headers or None, **connect_kw)
        except Exception as exc:
            _LOG.warning("autopulse_embedded_proxy_ws_connect_failed uri=%s err=%s", uri, exc)
            await send({"type": "websocket.close", "code": 1011})
            return

        subprotocol = upstream.subprotocol if getattr(upstream, "subprotocol", None) else None
        await send({"type": "websocket.accept", "subprotocol": subprotocol})

        async def pump_client_to_upstream() -> None:
            try:
                while True:
                    msg = await receive()
                    t = msg.get("type")
                    if t == "websocket.receive":
                        if "bytes" in msg and msg["bytes"] is not None:
                            await upstream.send(msg["bytes"])
                        elif "text" in msg and msg["text"] is not None:
                            await upstream.send(msg["text"])
                    elif t == "websocket.disconnect":
                        await upstream.close()
                        break
            except Exception:
                with suppress(Exception):
                    await upstream.close()

        async def pump_upstream_to_client() -> None:
            try:
                while True:
                    try:
                        message = await upstream.recv()
                    except ConnectionClosed:
                        break
                    if isinstance(message, str):
                        await send({"type": "websocket.send", "text": message})
                    else:
                        await send({"type": "websocket.send", "bytes": message})
            except Exception as exc:
                _LOG.debug("autopulse_embedded_proxy_ws_upstream_to_client: %s", exc)
            finally:
                with suppress(Exception):
                    await send({"type": "websocket.close", "code": 1000})

        await asyncio.gather(pump_client_to_upstream(), pump_upstream_to_client())
        with suppress(Exception):
            await upstream.close()
