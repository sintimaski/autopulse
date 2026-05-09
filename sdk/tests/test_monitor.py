import asyncio
import gzip
import json as json_std
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
from client_lifespan import lifespan_test_client
from fastapi import FastAPI, Response

from lumonox._infrastructure import InfrastructureSampler
from lumonox._monitor import (
    _build_infrastructure_widget_payload,
    _EventDispatcher,
    _LumonoxMiddleware,
    _MonitorConfig,
    _stable_error_hash,
    monitor,
)


def _resolved_json_payload(
    *,
    json: dict[str, Any] | None,
    content: bytes | None,
    headers: dict[str, str],
) -> dict[str, Any]:
    if json is not None:
        return json
    if content is None:
        return {}
    enc = (headers or {}).get("Content-Encoding", "")
    raw = gzip.decompress(content) if enc.lower().startswith("gzip") else content
    return json_std.loads(raw.decode("utf-8"))


def test_infrastructure_widget_payload_converts_network_bytes_to_mb() -> None:
    """NIC counters use _recv/_sent keys, so they skip endswith('_bytes') byte conversion."""
    payload = _build_infrastructure_widget_payload(
        {
            "network_bytes_recv": 524_288_000.0,
            "network_bytes_sent": 1_048_576.0,
        }
    )
    by_widget = {p["widget_id"]: float(p["value"]) for p in payload["points"]}
    assert by_widget["infra_network_received_mb"] == pytest.approx(500.0)
    assert by_widget["infra_network_sent_mb"] == pytest.approx(1.0)


def test_infrastructure_sampler_permission_error_fails_soft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PsutilPermissionErrorStub:
        @staticmethod
        def Process() -> object:
            return object()

        @staticmethod
        def virtual_memory() -> object:
            return object()

        @staticmethod
        def disk_usage(_path: str) -> object:
            return object()

        @staticmethod
        def disk_io_counters() -> object:
            return object()

        @staticmethod
        def net_io_counters() -> object:
            raise PermissionError("sysctl denied")

    monkeypatch.setattr("lumonox._infrastructure.psutil", _PsutilPermissionErrorStub)
    sampler = InfrastructureSampler(ttl_seconds=0.0)
    assert sampler.sample() == {}
    # Repeated failures should remain non-fatal.
    assert sampler.sample() == {}


def _make_config(**overrides: Any) -> _MonitorConfig:
    values = {
        "api_key": "ap_test_key",
        "ingest_url": "https://example.test/ingest",
        "startup_ingest_ping": False,
        "service_name": "test-api",
        "environment": "test",
        "queue_maxsize": 10,
        "batch_size": 2,
        "flush_interval_s": 0.05,
        "max_retries": 2,
        "retry_backoff_s": 0.0,
        "debug": False,
        "mount_prefix": None,
        "capture_headers": True,
        "capture_query_params": True,
        "scrub_keys": frozenset({"authorization", "cookie", "token", "api_key"}),
        "request_sample_rate": 1.0,
        "ignore_path_prefixes": (),
        "dashboard_widgets": tuple(),
        "infrastructure_sampler": None,
        "infrastructure_probe_interval_s": 0.0,
        "dashboard_widgets_attach_interval_s": 0.0,
    }
    values.update(overrides)
    return _MonitorConfig(**values)


@dataclass
class _CapturingDispatcher:
    events: list[dict[str, Any]] = field(default_factory=list)

    def enqueue(self, event: dict[str, Any]) -> None:
        self.events.append(event)


@dataclass
class _StaticInfrastructureSampler:
    payload: dict[str, Any]

    def sample(self) -> dict[str, Any]:
        return dict(self.payload)


def test_middleware_dashboard_widgets_attach_throttles() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config(
        infrastructure_sampler=_StaticInfrastructureSampler({"host_cpu_percent": 1.0}),
        dashboard_widgets_attach_interval_s=3600.0,
    )
    app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/a")
    async def a() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/b")
    async def b() -> dict[str, bool]:
        return {"ok": True}

    with lifespan_test_client(app) as client:
        assert client.get("/a").status_code == 200
        assert client.get("/b").status_code == 200

    assert len(dispatcher.events) == 2
    assert "dashboard_widgets" in dispatcher.events[0]
    assert "dashboard_widgets" not in dispatcher.events[1]


@dataclass
class _FailingClient:
    failures_before_success: int
    calls: int = 0
    sent_payloads: list[dict[str, Any]] = field(default_factory=list)

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str],
        **_: Any,
    ) -> httpx.Response:
        self.calls += 1
        payload = _resolved_json_payload(json=json, content=content, headers=headers)
        self.sent_payloads.append({"url": url, "json": payload, "headers": headers})
        if self.calls <= self.failures_before_success:
            raise httpx.ConnectError("temporary failure")
        request = httpx.Request("POST", url)
        accepted = len(payload.get("events", []))
        return httpx.Response(200, request=request, json={"accepted": accepted})


@dataclass
class _AlwaysFailingClient:
    calls: int = 0

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str],
        **_: Any,
    ) -> httpx.Response:
        self.calls += 1
        raise httpx.ConnectError("backend unavailable")


@dataclass
class _ErrorStatusClient:
    calls: int = 0

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str],
        **_: Any,
    ) -> httpx.Response:
        self.calls += 1
        request = httpx.Request("POST", url)
        return httpx.Response(503, request=request, json={"detail": "unavailable"})


@dataclass
class _UnauthorizedStatusClient:
    calls: int = 0

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str],
        **_: Any,
    ) -> httpx.Response:
        self.calls += 1
        request = httpx.Request("POST", url)
        return httpx.Response(401, request=request, json={"detail": "Invalid API key"})


@dataclass
class _PayloadTooLargeStatusClient:
    calls: int = 0

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str],
        **_: Any,
    ) -> httpx.Response:
        self.calls += 1
        request = httpx.Request("POST", url)
        return httpx.Response(413, request=request, json={"detail": "too large"})


@dataclass
class _RetryAfterStatusClient:
    calls: int = 0

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str],
        **_: Any,
    ) -> httpx.Response:
        self.calls += 1
        request = httpx.Request("POST", url)
        if self.calls == 1:
            return httpx.Response(
                429,
                request=request,
                headers={"Retry-After": "4"},
                json={"detail": "rate limited"},
            )
        return httpx.Response(200, request=request, json={"accepted": 1})


def test_monitor_is_noop_for_non_fastapi_object() -> None:
    monitor(object())


def test_monitor_rolls_back_when_startup_handler_registration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    middleware_before = len(app.user_middleware)
    startup_before = len(app.router.on_startup)
    shutdown_before = len(app.router.on_shutdown)

    monkeypatch.setattr("lumonox._monitor._add_event_handler", lambda *_args, **_kwargs: False)
    monitor(app, api_key="k", ingest_url="https://example.test/ingest")

    assert len(app.user_middleware) == middleware_before
    assert len(app.router.on_startup) == startup_before
    assert len(app.router.on_shutdown) == shutdown_before
    assert getattr(app.state, "_lumonox_configured", False) is False


def test_monitor_rolls_back_when_shutdown_handler_registration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    middleware_before = len(app.user_middleware)
    startup_before = len(app.router.on_startup)
    shutdown_before = len(app.router.on_shutdown)
    calls = {"n": 0}

    def _add_event_handler_once_then_fail(*_args: Any, **_kwargs: Any) -> bool:
        calls["n"] += 1
        return calls["n"] == 1

    monkeypatch.setattr("lumonox._monitor._add_event_handler", _add_event_handler_once_then_fail)
    monitor(app, api_key="k", ingest_url="https://example.test/ingest")

    assert len(app.user_middleware) == middleware_before
    assert len(app.router.on_startup) == startup_before
    assert len(app.router.on_shutdown) == shutdown_before
    assert getattr(app.state, "_lumonox_configured", False) is False


def test_monitor_rolls_back_handlers_when_middleware_attach_fails() -> None:
    app = FastAPI()
    middleware_before = len(app.user_middleware)
    startup_before = len(app.router.on_startup)
    shutdown_before = len(app.router.on_shutdown)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("middleware attach failed")

    app.add_middleware = _boom  # type: ignore[method-assign]
    monitor(app, api_key="k", ingest_url="https://example.test/ingest")

    assert len(app.user_middleware) == middleware_before
    assert len(app.router.on_startup) == startup_before
    assert len(app.router.on_shutdown) == shutdown_before
    assert getattr(app.state, "_lumonox_configured", False) is False


def test_middleware_records_wire_path_when_request_is_under_mount_prefix() -> None:
    main = FastAPI()
    inner = FastAPI()

    @inner.get("/dashboard/health")
    async def inner_health() -> dict[str, str]:
        return {"ok": "true"}

    main.mount("/lumonox", inner)
    dispatcher = _CapturingDispatcher()
    config = _make_config(mount_prefix="/lumonox")
    main.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    with lifespan_test_client(main) as client:
        response = client.get("/lumonox/dashboard/health")

    assert response.status_code == 200
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0]["path"] == "/lumonox/dashboard/health"


def test_middleware_captures_request_event_with_route_template() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config()
    app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/items/{item_id}")
    async def read_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    with lifespan_test_client(app) as client:
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


def test_middleware_respects_capture_toggles() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config(capture_headers=False, capture_query_params=False)
    app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/items/{item_id}")
    async def read_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    with lifespan_test_client(app) as client:
        response = client.get("/items/123?token=secret", headers={"authorization": "Bearer abc"})

    assert response.status_code == 200
    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert "headers" not in event
    assert "query_params" not in event


def test_middleware_ignores_configured_path_prefixes() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config(ignore_path_prefixes=("/health",))
    app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    with lifespan_test_client(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert dispatcher.events == []


def test_middleware_sampling_drops_success_events_but_keeps_5xx() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config(request_sample_rate=0.0)
    app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/ok")
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/server-error")
    async def server_error() -> Response:
        return Response(status_code=503)

    with lifespan_test_client(app) as client:
        ok_response = client.get("/ok")
        error_response = client.get("/server-error")

    assert ok_response.status_code == 200
    assert error_response.status_code == 503
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0]["path"] == "/server-error"
    assert dispatcher.events[0]["status_code"] == 503


def test_middleware_attaches_infrastructure_metrics_when_enabled() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config(
        infrastructure_sampler=_StaticInfrastructureSampler(
            payload={
                "host_cpu_percent": 35.0,
                "process_memory_percent": 3.1,
                "process_memory_rss_bytes": 157286400.0,
            }
        )
    )
    app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/status")
    async def status() -> dict[str, bool]:
        return {"ok": True}

    with lifespan_test_client(app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert "infrastructure_metrics" in event
    assert event["infrastructure_metrics"]["host_cpu_percent"] == 35.0
    assert event["infrastructure_metrics"]["process_memory_percent"] == 3.1
    widgets = event.get("dashboard_widgets")
    assert isinstance(widgets, dict)
    definitions = widgets.get("definitions", [])
    points = widgets.get("points", [])
    assert any(item.get("widget_id") == "infra_host_cpu_percent" for item in definitions)
    infra_cpu_points = [
        point for point in points if point.get("widget_id") == "infra_host_cpu_percent"
    ]
    assert infra_cpu_points
    assert float(infra_cpu_points[0]["value"]) == 35.0


def test_dispatcher_emits_infrastructure_probe_events() -> None:
    async def run() -> None:
        config = _make_config(
            batch_size=1,
            flush_interval_s=10.0,
            infrastructure_sampler=_StaticInfrastructureSampler(
                payload={
                    "host_cpu_percent": 31.5,
                    "host_memory_used_percent": 72.2,
                    "process_memory_percent": 2.9,
                    "process_memory_rss_bytes": 160000000.0,
                    "disk_used_percent": 61.0,
                    "network_bytes_recv": 500000000.0,
                    "network_bytes_sent": 125000000.0,
                }
            ),
            infrastructure_probe_interval_s=0.05,
        )
        client = _FailingClient(failures_before_success=0)
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher.start()
        await asyncio.sleep(0.12)
        await dispatcher.stop()
        flattened_events = [
            event for payload in client.sent_payloads for event in payload["json"].get("events", [])
        ]
        probe_events = [
            event
            for event in flattened_events
            if event.get("path") == "/lumonox/internal/infrastructure-probe"
        ]
        assert probe_events
        first = probe_events[0]
        assert "dashboard_widgets" in first
        assert "infrastructure_metrics" in first
        definitions = first["dashboard_widgets"]["definitions"]
        assert any(item.get("widget_id") == "infra_host_cpu_percent" for item in definitions)

    asyncio.run(run())


def test_middleware_captures_error_and_reraises_original_exception() -> None:
    app = FastAPI()
    dispatcher = _CapturingDispatcher()
    config = _make_config()
    app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)

    @app.get("/boom/{item_id}")
    async def explode(item_id: int) -> dict[str, int]:
        raise ValueError(f"bad item: {item_id}")

    with (
        lifespan_test_client(app, raise_server_exceptions=True) as client,
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


def test_dispatcher_scrubs_additional_sensitive_key_variants() -> None:
    config = _make_config(scrub_keys=frozenset({"authorization", "id_token"}))
    dispatcher = _EventDispatcher(config, client=_FailingClient(failures_before_success=0))
    dispatcher.enqueue({"headers": {"x-id-token": "secret-123"}})
    queued = dispatcher._queue.get_nowait()
    assert queued["headers"]["x-id-token"] == "[REDACTED]"


def test_send_batch_retries_then_succeeds() -> None:
    async def run() -> None:
        config = _make_config(max_retries=3)
        client = _FailingClient(failures_before_success=2)
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher._send_batch([{"type": "request"}])
        assert client.calls == 3
        assert client.sent_payloads[-1]["headers"]["Authorization"] == "Bearer ap_test_key"
        assert "Idempotency-Key" in client.sent_payloads[-1]["headers"]
        idem_values = [payload["headers"]["Idempotency-Key"] for payload in client.sent_payloads]
        assert len(set(idem_values)) == 1
        assert "sdk_version" in client.sent_payloads[-1]["json"]

    asyncio.run(run())


def test_send_batch_drops_after_retries_exhausted() -> None:
    async def run() -> None:
        config = _make_config(max_retries=2, retry_backoff_s=0.0)
        client = _AlwaysFailingClient()
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher._send_batch([{"type": "request"}])
        assert client.calls == 3

    asyncio.run(run())


def test_send_batch_retries_on_http_error_status() -> None:
    async def run() -> None:
        config = _make_config(max_retries=1, retry_backoff_s=0.0)
        client = _ErrorStatusClient()
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher._send_batch([{"type": "request"}])
        assert client.calls == 2

    asyncio.run(run())


def test_send_batch_does_not_retry_on_401() -> None:
    async def run() -> None:
        config = _make_config(max_retries=3, retry_backoff_s=0.0)
        client = _UnauthorizedStatusClient()
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher._send_batch([{"type": "request"}])
        assert client.calls == 1

    asyncio.run(run())


def test_send_batch_does_not_retry_on_non_retryable_4xx() -> None:
    async def run() -> None:
        config = _make_config(max_retries=3, retry_backoff_s=0.0)
        client = _PayloadTooLargeStatusClient()
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher._send_batch([{"type": "request"}])
        assert client.calls == 1

    asyncio.run(run())


def test_send_batch_honors_retry_after_for_429(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    async def run() -> None:
        config = _make_config(max_retries=2, retry_backoff_s=0.0)
        client = _RetryAfterStatusClient()
        dispatcher = _EventDispatcher(config, client=client)
        await dispatcher._send_batch([{"type": "request"}])
        assert client.calls == 2

    asyncio.run(run())
    assert slept == [4.0]


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


def test_monitor_request_path_remains_healthy_when_backend_is_down() -> None:
    app = FastAPI()
    failing_client = _AlwaysFailingClient()
    monitor(
        app,
        api_key="ap_live_xxx_secret",
        ingest_url="https://example.test/ingest",
        http_client=failing_client,
        batch_size=1,
        flush_interval_s=0.01,
        max_retries=1,
        retry_backoff_s=0.0,
    )

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    with lifespan_test_client(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        time.sleep(0.05)


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
    hash_a = _stable_error_hash("ValueError", "boom", stack_a, "/api/a")
    hash_b = _stable_error_hash("ValueError", "boom", stack_b, "/api/a")
    assert hash_a == hash_b


def test_stable_error_hash_differs_by_path() -> None:
    stack = "ValueError: boom\n"
    h_a = _stable_error_hash("ValueError", "boom", stack, "/boom")
    h_b = _stable_error_hash("ValueError", "boom", stack, "/orders")
    assert h_a != h_b


def test_monitor_warns_and_ignores_deprecated_embedded_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    app = FastAPI()
    with caplog.at_level(logging.WARNING):
        monitor(app, mode="embedded", api_key="k", ingest_url="http://127.0.0.1:8000/ingest")
    assert any("mode='embedded' is no longer supported" in r.message for r in caplog.records)
