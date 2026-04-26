from __future__ import annotations

import argparse
import hashlib
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _build_events(now: datetime, service_name: str, environment: str) -> list[dict[str, Any]]:
    # Fixed shape and ordering keeps dashboard output deterministic across runs.
    specs = [
        ("GET", "/health", 200, 12.5),
        ("GET", "/items/1", 200, 19.4),
        ("POST", "/items", 201, 34.8),
        ("GET", "/missing-route", 404, 11.2),
        ("GET", "/missing-route", 404, 10.9),
        ("GET", "/boom", 500, 55.1),
        ("POST", "/boom", 502, 66.7),
        ("GET", "/slow", 200, 180.0),
    ]
    events: list[dict[str, Any]] = []
    for idx, (method, path, status_code, latency_ms) in enumerate(specs):
        timestamp = now - timedelta(minutes=(len(specs) - idx))
        event_type = "error" if status_code >= 500 else "request"
        row: dict[str, Any] = {
            "type": event_type,
            "timestamp": _iso(timestamp),
            "service_name": service_name,
            "environment": environment,
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "request_id": f"manual-{idx + 1:02d}",
        }
        if event_type == "error":
            exc_type = "ManualTestError"
            exc_msg = f"Simulated failure for {method} {path} ({status_code})"
            stack = f"Traceback (manual test):\n  {path}:{status_code}\n"
            digest = hashlib.sha256()
            digest.update(exc_type.encode())
            digest.update(b"|")
            digest.update(exc_msg.encode())
            digest.update(b"|")
            digest.update(stack.encode())
            row["exception_type"] = exc_type
            row["exception_message"] = exc_msg
            row["stack_trace"] = stack
            row["error_hash"] = digest.hexdigest()
        events.append(row)
    return events


def _resolve_api_key(cli_value: str | None) -> str:
    key = (cli_value or os.environ.get("AUTOPULSE_API_KEY", "")).strip()
    if not key:
        raise SystemExit(
            "Missing API key: pass --api-key or set AUTOPULSE_API_KEY "
            "(same value as NEXT_PUBLIC_AUTOPULSE_API_KEY in frontend/.env.local)."
        )
    if key in ("YOUR_REAL_KEY", "ap_live_your_key_here"):
        raise SystemExit(
            f"Replace placeholder API key {key!r} with a real key from your backend database "
            "(the ap_live_... string you created for this project)."
        )
    return key


def _raise_http(message: str, response: httpx.Response) -> None:
    detail = response.text.strip() or "(empty body)"
    raise SystemExit(f"{message}: HTTP {response.status_code}\n{detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send deterministic dashboard test traffic to a running AutoPulse backend."
    )
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument(
        "--api-key",
        default=None,
        help="Bearer token (ap_live_...). If omitted, uses AUTOPULSE_API_KEY from the environment.",
    )
    parser.add_argument("--service-name", default="manual-test-api")
    parser.add_argument("--environment", default="dev")
    args = parser.parse_args()

    api_key = _resolve_api_key(args.api_key)

    now = datetime.now(tz=UTC)
    events = _build_events(now, args.service_name, args.environment)
    headers = {"Authorization": f"Bearer {api_key}"}
    ingest_payload = {"sdk_version": "manual-test-1.0", "events": events}
    base_url = args.api_base_url.rstrip("/")

    with httpx.Client(timeout=10.0) as client:
        ingest_response = client.post(f"{base_url}/ingest", json=ingest_payload, headers=headers)
        if ingest_response.status_code == 401:
            _raise_http(
                "Ingest rejected (401). Key must match api_keys for this backend's DATABASE_URL",
                ingest_response,
            )
        if not ingest_response.is_success:
            _raise_http("Ingest failed", ingest_response)

        params = {
            "from_timestamp": _iso(now - timedelta(minutes=30)),
            "to_timestamp": _iso(now + timedelta(minutes=1)),
            "limit": "50",
        }
        overview_response = client.get(
            f"{base_url}/dashboard/overview", params=params, headers=headers
        )
        if not overview_response.is_success:
            _raise_http("Dashboard overview failed", overview_response)
        requests_response = client.get(
            f"{base_url}/dashboard/requests", params=params, headers=headers
        )
        if not requests_response.is_success:
            _raise_http("Dashboard requests failed", requests_response)

    overview = overview_response.json()
    requests_payload = requests_response.json()
    request_items = requests_payload.get("items", [])
    status_counts: dict[int, int] = {}
    for item in request_items:
        code = int(item["status_code"])
        status_counts[code] = status_counts.get(code, 0) + 1

    print("manual_dashboard_test result")
    print(f"- accepted_events: {ingest_response.json().get('accepted')}")
    print(f"- dashboard_request_count: {overview.get('request_count')}")
    print(f"- dashboard_error_count: {overview.get('error_count')} (5xx only)")
    print(f"- dashboard_recent_items: {len(request_items)}")
    print("- status_counts:")
    for code in sorted(status_counts):
        print(f"  - {code}: {status_counts[code]}")
    print("- expected_404_count: 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
