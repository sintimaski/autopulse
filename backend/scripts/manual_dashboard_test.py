from __future__ import annotations

import argparse
import os
import random
import signal
import time
from datetime import UTC, datetime, timedelta

import httpx

from autopulse_backend.scenario_events import (
    generate_manual_batch_events,
    split_csv_values,
)

_KEEP_RUNNING = True


def _handle_stop_signal(_signum: int, _frame: object) -> None:
    global _KEEP_RUNNING
    _KEEP_RUNNING = False


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


def _fetch_dashboard_snapshot(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    now: datetime,
) -> tuple[int | None, int | None]:
    params = {
        "from_timestamp": _iso(now - timedelta(minutes=30)),
        "to_timestamp": _iso(now + timedelta(minutes=1)),
        "limit": "50",
    }
    overview_response = client.get(f"{base_url}/dashboard/overview", params=params, headers=headers)
    if not overview_response.is_success:
        _raise_http("Dashboard overview failed", overview_response)
    overview = overview_response.json()
    return overview.get("request_count"), overview.get("error_count")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Continuously send dashboard test traffic to a running AutoPulse backend."
    )
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument(
        "--api-key",
        default=None,
        help="Bearer token (ap_live_...). If omitted, uses AUTOPULSE_API_KEY from the environment.",
    )
    parser.add_argument("--service-name", default="manual-test-api")
    parser.add_argument("--environment", default="dev")
    parser.add_argument(
        "--service-pool",
        default="",
        help="Optional comma-separated services to rotate (overrides --service-name).",
    )
    parser.add_argument(
        "--environment-pool",
        default="",
        help="Optional comma-separated environments to rotate (overrides --environment).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=12,
        help="Number of events per ingest call.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=2.0,
        help="Delay between ingest calls.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Stop after N batches. Use 0 to run forever (recommended for background mode).",
    )
    parser.add_argument(
        "--verify-every",
        type=int,
        default=10,
        help="Fetch dashboard overview every N batches. Use 0 to disable checks.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible traffic shape.",
    )
    parser.add_argument(
        "--spike-chance",
        type=float,
        default=0.2,
        help="Chance each batch becomes a burst (0-1).",
    )
    parser.add_argument(
        "--spike-multiplier",
        type=float,
        default=2.4,
        help="Multiplier applied during burst batches.",
    )
    args = parser.parse_args()

    api_key = _resolve_api_key(args.api_key)
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if args.interval_seconds < 0:
        raise SystemExit("--interval-seconds must be >= 0")
    if args.max_batches < 0:
        raise SystemExit("--max-batches must be >= 0")
    if args.verify_every < 0:
        raise SystemExit("--verify-every must be >= 0")
    if args.spike_chance < 0 or args.spike_chance > 1:
        raise SystemExit("--spike-chance must be between 0 and 1")
    if args.spike_multiplier < 1:
        raise SystemExit("--spike-multiplier must be >= 1")

    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = args.api_base_url.rstrip("/")
    rng = random.Random(args.seed)  # nosec B311 - deterministic synthetic traffic generator
    service_pool = split_csv_values(args.service_pool) or (args.service_name,)
    environment_pool = split_csv_values(args.environment_pool) or (args.environment,)
    signal.signal(signal.SIGINT, _handle_stop_signal)
    signal.signal(signal.SIGTERM, _handle_stop_signal)

    sent_batches = 0
    sent_events = 0
    started_at = time.monotonic()

    try:
        with httpx.Client(timeout=10.0) as client:
            print("manual_dashboard_test: started traffic generator")
            print(f"- api_base_url: {base_url}")
            print(f"- service_name: {args.service_name}")
            print(f"- environment: {args.environment}")
            print(f"- service_pool: {', '.join(service_pool)}")
            print(f"- environment_pool: {', '.join(environment_pool)}")
            print(f"- batch_size: {args.batch_size}")
            print(f"- interval_seconds: {args.interval_seconds}")
            print(f"- max_batches: {'infinite' if args.max_batches == 0 else args.max_batches}")
            print(f"- verify_every: {args.verify_every}")
            print(f"- spike_chance: {args.spike_chance}")
            print(f"- spike_multiplier: {args.spike_multiplier}")
            while _KEEP_RUNNING:
                if args.max_batches and sent_batches >= args.max_batches:
                    break

                now = datetime.now(tz=UTC)
                events, batch_stats = generate_manual_batch_events(
                    now=now,
                    batch_index=sent_batches + 1,
                    batch_size=args.batch_size,
                    rng=rng,
                    service_names=service_pool,
                    environments=environment_pool,
                    spike_chance=args.spike_chance,
                    spike_multiplier=args.spike_multiplier,
                )
                ingest_payload = {"sdk_version": "manual-test-2.0", "events": events}
                ingest_response = client.post(
                    f"{base_url}/ingest", json=ingest_payload, headers=headers
                )
                if ingest_response.status_code == 401:
                    _raise_http(
                        "Ingest rejected (401). Key must match api_keys for this backend's "
                        "DATABASE_URL",
                        ingest_response,
                    )
                if not ingest_response.is_success:
                    _raise_http("Ingest failed", ingest_response)

                sent_batches += 1
                accepted_events = int(ingest_response.json().get("accepted", 0))
                sent_events += accepted_events
                msg = (
                    f"batch={sent_batches} accepted={accepted_events} total_sent={sent_events} "
                    f"spike_windows={batch_stats.spike_windows}"
                )
                if args.verify_every and sent_batches % args.verify_every == 0:
                    request_count, error_count = _fetch_dashboard_snapshot(
                        client=client,
                        base_url=base_url,
                        headers=headers,
                        now=now,
                    )
                    msg += f" dashboard_requests={request_count} dashboard_errors={error_count}"
                print(msg, flush=True)

                if args.interval_seconds > 0:
                    time.sleep(args.interval_seconds)
    except httpx.ConnectError as exc:
        raise SystemExit(
            f"Cannot connect to {base_url} ({exc}). "
            "Start the API from the repo root (`uv run python -m autopulse_backend.main`) "
            "or pass --api-base-url if the server uses another host/port."
        ) from exc

    elapsed = round(time.monotonic() - started_at, 2)
    print("manual_dashboard_test: stopped")
    print(f"- batches_sent: {sent_batches}")
    print(f"- events_accepted: {sent_events}")
    print(f"- elapsed_seconds: {elapsed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
