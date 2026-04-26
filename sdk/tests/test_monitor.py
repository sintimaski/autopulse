import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopulse._monitor import (
    _AutoPulseMiddleware,
    _EventDispatcher,
    _MonitorConfig,
    _stable_error_hash,
    monitor,
)


def _make_config(**overrides: Any) -> _MonitorConfig:
    values = {
        "api_key": "ap_test_key",
        "ingest_url": "https://example.test/ingest",
        "service_name": "test-api",
        "environment": "test",
        "queue_maxsize": 10,
        "batch_size": 2,
        "flush_interval_s": 0.05,
        "max_retries": 2,
        "retry_backoff_s": 0.0,
        "debug": False,
    }
    values.update(overrides)
    return _MonitorConfig(**values)


@dataclass
class _CapturingDispatcher:
    events: list[dict[str, Any]] = field(default_factory=list)

    def enqueue(self, event: dict[str, Any]) -> None:
        self.events.append(event)


@dataclass
class _FailingClient:
    failures_before_success: int
    calls: int = 0
    sent_payloads: list[dict[str, Any]] = field(default_factory=list)

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        self.calls += 1
        self.sent_payloads.append({"url": url, "json": json, "headers": headers})
        if self.calls <= self.failures_before_success:
            raise httpx.ConnectError("temporary failure")
        request = httpx.Request("POST", url)
        return httpx.Response(200, request=request, json={"accepted": len(json.get("events", []))})


def test_monitor_is_noop_for_non_fastapi_object() -> None:
    monitor(object())


def test_middleware_captures_request_event_with_route_template() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config()
    app.add_middleware(_AutoPulseMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/items/{item_id}")
    async def read_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    with TestClient(app) as client:
        response = client.get(
            "/items/123?token=secret",
            headers={"x-request-id": "req-123", "authorization": "Bearer abc"},
        )

    assert response.status_code == 200
    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert event["type"] == "request"
    assert event["path"] == "/items/{item_id}"
    assert event["status_code"] == 200
    assert event["request_id"] == "req-123"
    assert isinstance(event["latency_ms"], float)


def test_middleware_captures_error_and_reraises_original_exception() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config()
    app.add_middleware(_AutoPulseMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/boom/{item_id}")
    async def explode(item_id: int) -> dict[str, int]:
        raise ValueError(f"bad item: {item_id}")

    with (
        TestClient(app, raise_server_exceptions=True) as client,
        pytest.raises(ValueError, match="bad item: 10"),
    ):
        client.get("/boom/10")

    assert len(dispatcher.events) == 2
    request_event, error_event = dispatcher.events
    assert request_event["type"] == "request"
    assert request_event["status_code"] == 500
    assert error_event["type"] == "error"
    assert error_event["exception_type"] == "ValueError"
    assert "bad item: 10" in error_event["exception_message"]
    assert error_event["path"] == "/boom/{item_id}"
    assert error_event["error_hash"]


def test_dispatcher_drops_when_queue_is_full() -> None:
    config = _make_config(queue_maxsize=1)
    dispatcher = _EventDispatcher(config, client=_FailingClient(failures_before_success=0))
    dispatcher.enqueue({"type": "request", "headers": {"authorization": "a"}})
    dispatcher.enqueue({"type": "request", "headers": {"authorization": "b"}})
    assert dispatcher._queue.qsize() == 1


def test_dispatcher_scrubs_sensitive_fields_before_queueing() -> None:
    config = _make_config()
    dispatcher = _EventDispatcher(config, client=_FailingClient(failures_before_success=0))
    dispatcher.enqueue(
        {
            "type": "request",
            "headers": {"authorization": "Bearer token"},
            "query_params": {"api_key": "abc", "search": "ok"},
            "nested": {"token": "secret"},
        }
    )
    queued = dispatcher._queue.get_nowait()
    assert queued["headers"]["authorization"] == "[REDACTED]"
    assert queued["query_params"]["api_key"] == "[REDACTED]"
    assert queued["query_params"]["search"] == "ok"
    assert queued["nested"]["token"] == "[REDACTED]"


def test_send_batch_retries_then_succeeds() -> None:
    async def run() -> None:
        config = _make_config(max_retries=3)
        client = _FailingClient(failures_before_success=2)
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher._send_batch([{"type": "request"}])
        assert client.calls == 3
        assert client.sent_payloads[-1]["headers"]["Authorization"] == "Bearer ap_test_key"
        assert "sdk_version" in client.sent_payloads[-1]["json"]

    asyncio.run(run())


def test_sender_loop_flushes_on_batch_size() -> None:
    async def run() -> None:
        config = _make_config(batch_size=2, flush_interval_s=10.0)
        client = _FailingClient(failures_before_success=0)
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher.start()
        dispatcher.enqueue({"type": "request", "headers": {"authorization": "a"}})
        dispatcher.enqueue({"type": "request", "headers": {"authorization": "b"}})
        await asyncio.sleep(0.05)
        await dispatcher.stop()
        assert client.calls == 1
        events = client.sent_payloads[0]["json"]["events"]
        assert len(events) == 2
        assert events[0]["headers"]["authorization"] == "[REDACTED]"

    asyncio.run(run())


def test_stable_error_hash_ignores_stack_line_numbers() -> None:
    stack_a = """Traceback (most recent call last):
  File "/app/api.py", line 12, in endpoint
    do_work()
ValueError: boom
"""
    stack_b = """Traceback (most recent call last):
  File "/app/api.py", line 98, in endpoint
    do_work()
ValueError: boom
"""
    hash_a = _stable_error_hash("ValueError", "boom", stack_a)
    hash_b = _stable_error_hash("ValueError", "boom", stack_b)
    assert hash_a == hash_b
