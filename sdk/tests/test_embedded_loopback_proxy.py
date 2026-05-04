from __future__ import annotations

from autopulse._embedded_loopback_proxy import _websocket_upstream_additional_headers


def test_ws_proxy_headers_drop_handshake_fields_regenerated_by_client() -> None:
    scope_headers = [
        (b"cookie", b"autopulse_session=abc"),
        (b"Sec-WebSocket-Key", b"dGhlIHNhbXBsZSBub25jZQ=="),
        (b"Sec-WebSocket-Version", b"13"),
        (b"Sec-WebSocket-Extensions", b"permessage-deflate; client_max_window_bits"),
        (b"Sec-WebSocket-Protocol", b"chat"),
        (b"Origin", b"http://127.0.0.1:8000"),
    ]
    headers, origin = _websocket_upstream_additional_headers(
        scope_headers, upstream_host_header="127.0.0.1:9999"
    )
    names = {k.lower() for k, _ in headers}
    assert "sec-websocket-key" not in names
    assert "sec-websocket-version" not in names
    assert "sec-websocket-extensions" not in names
    assert "sec-websocket-protocol" not in names
    assert "origin" not in names
    assert ("Host", "127.0.0.1:9999") in headers
    assert ("Cookie", "autopulse_session=abc") in headers
    assert origin == "http://127.0.0.1:8000"


def test_ws_proxy_dedupes_case_insensitive_headers_last_wins() -> None:
    scope_headers = [
        (b"X-Request-Id", b"one"),
        (b"x-request-id", b"two"),
    ]
    headers, origin = _websocket_upstream_additional_headers(
        scope_headers, upstream_host_header="127.0.0.1:1"
    )
    assert origin is None
    assert [p for p in headers if p[0].lower() == "x-request-id"] == [("x-request-id", "two")]


def test_ws_proxy_merges_multiple_cookie_lines() -> None:
    scope_headers = [
        (b"Cookie", b"a=1"),
        (b"cookie", b"b=2"),
    ]
    headers, _origin = _websocket_upstream_additional_headers(
        scope_headers, upstream_host_header="127.0.0.1:1"
    )
    cookie_hdrs = [p for p in headers if p[0].lower() == "cookie"]
    assert cookie_hdrs == [("Cookie", "a=1; b=2")]
