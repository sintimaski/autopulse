"""End-to-end coverage of the lumonox.django adapter.

Uses an in-process Django ASGI app driven through ``httpx.ASGITransport``
plus an httpx ``MockTransport`` as the ingest stub. The dispatcher is
started/stopped manually around the test body (the same shape the
synthetic harness uses).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

pytest.importorskip("django")  # noqa: E402

# Reset the lumonox.django module-level slot between tests so a test that
# tweaks dispatcher config does not bleed into the next one.
from lumonox.django import middleware as django_middleware  # noqa: E402
from lumonox.django import monitor  # noqa: E402
from lumonox.fixtures.synthetic_django_app import create_asgi_app  # noqa: E402


@pytest.fixture
def captured_events() -> Iterator[list[dict[str, Any]]]:
    """Return a list ingest events get appended to during the test.

    Wires a ``httpx.MockTransport`` ingest stub into the dispatcher. Each POST
    is decoded (gzip-aware) and its ``events`` array is extended into the
    captured list.
    """
    events: list[dict[str, Any]] = []

    def _stub(request: httpx.Request) -> httpx.Response:
        raw = request.content or b""
        if request.headers.get("Content-Encoding") == "gzip":
            import gzip as _gzip

            raw = _gzip.decompress(raw)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            payload = {}
        for evt in payload.get("events", []):
            if isinstance(evt, dict):
                events.append(evt)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(_stub)
    stub_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    dispatcher = monitor(
        api_key="django-smoke-key",
        ingest_url="https://ingest.invalid/ingest",
        service_name="synthetic-django",
        environment="smoke",
        batch_size=1,
        flush_interval_s=0.05,
        queue_maxsize=200,
        capture_headers=True,
        capture_infrastructure_metrics=False,
        http_client=stub_client,
        owns_http_client=False,
    )
    yield events
    # Drain + tear down the dispatcher; close the stub client.
    asyncio.run(_shutdown_dispatcher(dispatcher, stub_client))
    django_middleware._Runtime.config = None
    django_middleware._Runtime.dispatcher = None
    django_middleware._Runtime._last_widgets_attach_monotonic = 0.0


async def _shutdown_dispatcher(dispatcher: Any, stub_client: httpx.AsyncClient) -> None:
    await dispatcher.stop()
    await stub_client.aclose()


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _start(dispatcher: Any) -> None:
    await dispatcher.start()


@pytest.mark.asyncio
async def test_django_adapter_captures_ok_and_error_paths(
    captured_events: list[dict[str, Any]],
) -> None:
    dispatcher = django_middleware._Runtime.dispatcher
    assert dispatcher is not None
    await dispatcher.start()

    app = create_asgi_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.get(
            "/users/42/",
            headers={
                "Authorization": "Bearer super-secret-token",
                "X-Request-ID": "rid-django-ok",
            },
        )
        assert ok.status_code == 200, ok.text
        assert ok.headers.get("x-request-id") == "rid-django-ok"

        # Django catches the view exception in its own middleware and converts
        # it to a 500 response — by design. Our adapter still has to emit a
        # rich ``type=error`` event with exception_type/message/hash, which it
        # gets from the ``got_request_exception`` signal we connected in
        # ``monitor()``.
        err = await client.get("/boom/", headers={"X-Request-ID": "rid-django-err"})
        assert err.status_code == 500, err.text

    # Stop will flush whatever is still in the queue.
    await dispatcher.stop()

    types_seen = {evt.get("type") for evt in captured_events}
    assert "request" in types_seen, captured_events
    assert "error" in types_seen, captured_events

    ok_event = next(
        (e for e in captured_events if e.get("path", "").startswith("/users/")),
        None,
    )
    assert ok_event is not None, captured_events
    assert ok_event["request_id"] == "rid-django-ok"
    # Header scrubbing must have happened before send.
    auth_value = (ok_event.get("headers") or {}).get("authorization") or (
        ok_event.get("headers") or {}
    ).get("Authorization")
    assert auth_value == "[REDACTED]", ok_event.get("headers")

    err_event = next(
        (e for e in captured_events if e.get("type") == "error" and e.get("path") == "/boom/"),
        None,
    )
    assert err_event is not None, captured_events
    assert err_event["exception_type"] == "RuntimeError"
    assert "synthetic django explosion" in err_event["exception_message"]
    assert err_event["request_id"] == "rid-django-err"
    assert err_event["error_hash"]
    assert err_event["stack_trace"]


def test_django_middleware_passthrough_when_monitor_not_called() -> None:
    """Without ``monitor()`` the middleware is a silent passthrough — never break the host."""
    django_middleware._Runtime.config = None
    django_middleware._Runtime.dispatcher = None

    # Build a minimal sync-ish coroutine that the middleware can wrap.
    sentinel = object()

    async def get_response(_request: Any) -> Any:
        return sentinel

    mw = django_middleware.LumonoxMiddleware(get_response)

    class _Req:
        method = "GET"
        path = "/anything"
        headers: dict[str, str] = {}
        GET: dict[str, str] = {}
        resolver_match = None

    result = asyncio.run(mw(_Req()))
    assert result is sentinel


def test_django_adapter_identity_matches_canonical_paths() -> None:
    """Adapter reuses the canonical core/ symbols, not its own copies."""
    from lumonox.core import dispatcher as core_dispatcher
    from lumonox.core import scrubbing as core_scrubbing

    assert django_middleware._EventDispatcher is core_dispatcher._EventDispatcher
    assert django_middleware._stable_error_hash is core_scrubbing.__dict__.get(
        "_stable_error_hash", django_middleware._stable_error_hash
    )  # _stable_error_hash lives in core.events; this checks the adapter pulled the canonical one
    from lumonox.core import events as core_events

    assert django_middleware._stable_error_hash is core_events._stable_error_hash
