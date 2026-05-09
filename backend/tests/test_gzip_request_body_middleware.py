"""Tests for gzip request-body ASGI middleware."""

from __future__ import annotations

import gzip
import json

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from lumonox_backend.middleware.gzip_request_body import GzipRequestBodyMiddleware


async def _echo_json(request: Request) -> JSONResponse:
    data = await request.json()
    return JSONResponse({"received": data})


@pytest.fixture
def gzip_decode_app() -> Starlette:
    app = Starlette(routes=[Route("/echo", _echo_json, methods=["POST"])])
    app.add_middleware(GzipRequestBodyMiddleware)
    return app


def test_gzip_request_body_is_decoded_for_json_route(gzip_decode_app: Starlette) -> None:
    payload = {"hello": "world", "n": 42}
    raw = json.dumps(payload).encode()
    compressed = gzip.compress(raw)
    client = TestClient(gzip_decode_app)
    response = client.post(
        "/echo",
        content=compressed,
        headers={
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"received": payload}


def test_plain_json_untouched(gzip_decode_app: Starlette) -> None:
    payload = {"x": 1}
    client = TestClient(gzip_decode_app)
    response = client.post("/echo", json=payload)
    assert response.status_code == 200
    assert response.json() == {"received": payload}


def test_invalid_gzip_returns_400(gzip_decode_app: Starlette) -> None:
    client = TestClient(gzip_decode_app)
    response = client.post(
        "/echo",
        content=b"not gzip",
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )
    assert response.status_code == 400


def test_create_app_registers_gzip_middleware() -> None:
    from starlette.middleware.gzip import GZipMiddleware

    from lumonox_backend.app import create_app
    from lumonox_backend.middleware.gzip_request_body import GzipRequestBodyMiddleware

    app = create_app()
    classes = [m.cls for m in app.user_middleware]
    assert GzipRequestBodyMiddleware in classes
    assert GZipMiddleware in classes


def test_response_gzip_when_payload_large_enough() -> None:
    """``GZipMiddleware`` only wraps bodies above ``minimum_size``."""
    from starlette.applications import Starlette
    from starlette.middleware.gzip import GZipMiddleware
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    async def big(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("x" * 900)

    app = Starlette(routes=[Route("/big", big)])
    app.add_middleware(GZipMiddleware, minimum_size=512, compresslevel=5)
    client = TestClient(app)
    response = client.get("/big", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    # httpx TestClient transparently decodes gzip bodies on read.
    assert response.content == b"x" * 900
