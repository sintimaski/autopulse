"""End-to-end smoke for ``lumonox-sdk``: real ingest stub, real SDK, real events.

The install matrix (``scripts/sdk_install_smoke.py``) verifies that the wheel
installs and that the public surface looks correct. This script goes one step
further: it boots an ASGI ingest stub, instruments a small FastAPI app with
``lumonox(app, …)`` over the canonical entry point, drives requests through
it (including a 500 path with a sensitive header), and asserts the events
that actually reach the stub. It is the lightweight stand-in for the plan's
"observe events arriving at a local backend" verification step — no docker,
no npm, no backend wheel build.

Run with: ``uv run python scripts/sdk_end_to_end_smoke.py`` from the repo root.
Exits non-zero on any failure with a human-readable explanation.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections import deque
from typing import Any
from wsgiref.simple_server import make_server

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Canonical import path; the legacy ``from lumonox import lumonox`` continues to
# resolve to the same object thanks to the re-export shims.
from lumonox import lumonox as instrument


def _ok(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  [ok] {label}{suffix}")


def _fail(label: str, detail: str) -> str:
    print(f"  [FAIL] {label} — {detail}", file=sys.stderr)
    sys.exit(1)


def _wsgi_ingest_app(received: deque[dict[str, Any]]) -> Any:
    def app(environ: dict[str, Any], start_response: Any) -> list[bytes]:
        # Drain the request body and decompress if gzip-encoded.
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length) if length else b""
        if environ.get("HTTP_CONTENT_ENCODING") == "gzip":
            import gzip

            body = gzip.decompress(body)
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {"_raw": body[:200]}
        received.append(payload)
        start_response("200 OK", [("Content-Type", "application/json")])
        return [b'{"ok": true}']

    return app


def _build_instrumented_app() -> FastAPI:
    app = FastAPI()

    @app.get("/users/{user_id}")
    def read_user(user_id: str) -> dict[str, str]:
        return {"id": user_id, "name": "demo"}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("synthetic explosion")

    return app


def main() -> None:
    print("lumonox-sdk end-to-end smoke")

    received: deque[dict[str, Any]] = deque()
    server = make_server("127.0.0.1", 0, _wsgi_ingest_app(received))
    host, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    ingest_url = f"http://{host}:{port}/ingest"
    print(f"  ingest stub listening on {ingest_url}")

    try:
        app = _build_instrumented_app()
        instrument(
            app,
            api_key="smoke-key",
            ingest_url=ingest_url,
            service_name="smoke-svc",
            environment="smoke",
            batch_size=1,
            flush_interval_s=0.05,
            queue_maxsize=100,
            capture_headers=True,
        )

        with TestClient(app, raise_server_exceptions=False) as client:
            r1 = client.get(
                "/users/42",
                headers={"Authorization": "Bearer super-secret-token", "X-Request-ID": "rid-1"},
            )
            r2 = client.get("/boom", headers={"X-Request-ID": "rid-2"})

            if r1.status_code != 200:
                _fail("ok-path status", f"expected 200, got {r1.status_code}")
            if r2.status_code != 500:
                _fail("error-path status", f"expected 500, got {r2.status_code}")
            if r1.headers.get("x-request-id") != "rid-1":
                _fail("x-request-id echo (ok)", f"got {r1.headers.get('x-request-id')!r}")
            # The error path re-raises the original exception by contract, so the
            # SDK never gets to stamp the response — Starlette's 500 fallback
            # has no ``X-Request-ID`` header. Correlation is still carried on the
            # captured ingest event below.
            _ok("response status + ok-path correlation header")

            # Wait for the async sender loop to drain. The TestClient context
            # manager exits the FastAPI shutdown handler which awaits the
            # dispatcher stop, so by the time we leave the ``with`` block any
            # buffered events have been flushed to the stub.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and len(received) < 2:
            time.sleep(0.05)

        events: list[dict[str, Any]] = []
        for batch in received:
            events.extend(batch.get("events", []) if isinstance(batch, dict) else [])
        if not events:
            _fail("ingest delivery", "no events reached the stub after 5 s")
        _ok("ingest delivery", f"received {len(received)} POST(s), {len(events)} event(s) total")

        request_events = [e for e in events if e.get("type") == "request"]
        error_events = [e for e in events if e.get("type") == "error"]
        if not request_events:
            _fail("event shape", "no type=request events in delivered payload")
        if not error_events:
            _fail("event shape", "no type=error events for the 500 path")
        _ok(
            "event shape",
            f"request_events={len(request_events)} error_events={len(error_events)}",
        )

        # Find the OK path and confirm authorization was scrubbed before send.
        ok_event = next(
            (e for e in request_events if e.get("path", "").startswith("/users/")),
            None,
        )
        if ok_event is None:
            _fail("ok-path event", "no event captured for /users/{user_id}")
        headers_seen = ok_event.get("headers") or {}
        auth_value = headers_seen.get("authorization") or headers_seen.get("Authorization")
        if auth_value != "[REDACTED]":
            _fail(
                "header scrubbing",
                f"Authorization should be [REDACTED] before send, got {auth_value!r}",
            )
        if ok_event.get("request_id") != "rid-1":
            _fail("correlation propagation (ok)", f"request_id={ok_event.get('request_id')!r}")
        _ok("scrubbing + correlation on ok-path event")

        err_event = next(
            (e for e in error_events if e.get("path") == "/boom"),
            None,
        )
        if err_event is None:
            _fail("error-path event", "no event captured for /boom")
        if err_event.get("exception_type") != "RuntimeError":
            _fail("error event shape", f"exception_type={err_event.get('exception_type')!r}")
        if "synthetic explosion" not in (err_event.get("exception_message") or ""):
            _fail("error event shape", "exception_message did not carry the original text")
        if err_event.get("request_id") != "rid-2":
            _fail("correlation propagation (err)", f"request_id={err_event.get('request_id')!r}")
        if not (err_event.get("stack_trace") or ""):
            _fail("error event shape", "stack_trace missing on error event")
        if not (err_event.get("error_hash") or ""):
            _fail("error event shape", "error_hash missing on error event")
        _ok("error event carries type+message+hash+correlation")

        print("OK — end-to-end smoke passed.")
    finally:
        # Stop the stub even if asserts above fired.
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
