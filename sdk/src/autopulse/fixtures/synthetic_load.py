from __future__ import annotations

import argparse
import random
import signal
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

_KEEP_RUNNING = True
RoleMode = Literal["viewer", "editor", "admin", "mixed"]


@dataclass(frozen=True, slots=True)
class RequestSpec:
    name: str
    method: str
    path_template: str
    weight: int


_REQUEST_SPECS: tuple[RequestSpec, ...] = (
    RequestSpec("health", "GET", "/health", 5),
    RequestSpec("users-read", "GET", "/users/{user_id}", 8),
    RequestSpec("users-create", "POST", "/users", 3),
    RequestSpec("users-patch", "PATCH", "/users/{user_id}", 3),
    RequestSpec("orders-read", "GET", "/orders/{order_id}", 8),
    RequestSpec("orders-create", "POST", "/orders", 4),
    RequestSpec("search", "GET", "/search", 7),
    RequestSpec("auth-login", "POST", "/auth/login", 3),
    RequestSpec("reports", "GET", "/reports/daily", 2),
    RequestSpec("boom", "GET", "/boom", 1),
)


def _handle_stop_signal(_signum: int, _frame: object) -> None:
    global _KEEP_RUNNING
    _KEEP_RUNNING = False


def _weighted_specs() -> list[RequestSpec]:
    weighted: list[RequestSpec] = []
    for spec in _REQUEST_SPECS:
        weighted.extend([spec] * spec.weight)
    return weighted


def _resolve_role(mode: RoleMode, *, rng: random.Random) -> str:
    if mode != "mixed":
        return mode
    return rng.choice(["viewer", "editor", "admin"])


def _auth_headers(role: str, *, request_id: str) -> dict[str, str]:
    return {
        "x-request-id": request_id,
        "x-auth-token": f"demo:{role}:{role}-bot",
    }


def _request_payload(
    *,
    spec: RequestSpec,
    rng: random.Random,
    request_id: str,
    request_index: int,
    error_burst: bool,
    role_mode: RoleMode,
) -> tuple[str, str, dict[str, Any], dict[str, str]]:
    role = _resolve_role(role_mode, rng=rng)
    headers = _auth_headers(role, request_id=request_id)
    params: dict[str, Any] = {}
    body: dict[str, Any] = {}
    user_id = rng.randint(1, 30)
    order_id = rng.randint(1000, 1100)
    path = spec.path_template.format(user_id=user_id, order_id=order_id)

    if spec.name == "users-create":
        suffix = request_index % 100_000
        body = {
            "email": f"user-{suffix}@example.com",
            "display_name": f"User {suffix}",
            "role": rng.choice(["viewer", "editor"]),
        }
        if error_burst and rng.random() < 0.3:
            body["email"] = "bad-email"
    elif spec.name == "users-patch":
        body = {
            "display_name": f"Patch {request_index}",
            "version": rng.randint(0, 4),
        }
        if error_burst and rng.random() < 0.5:
            params["force_conflict"] = "true"
    elif spec.name == "orders-create":
        body = {
            "user_id": user_id,
            "amount_cents": rng.randint(120, 9_999),
            "item": f"item-{rng.randint(1, 300)}",
        }
        if error_burst and rng.random() < 0.5:
            params["force_unavailable"] = "true"
    elif spec.name == "search":
        params["q"] = f"q-{rng.randint(1, 50)}"
    elif spec.name == "auth-login":
        chosen_role = rng.choice(["viewer", "editor", "admin"])
        body = {"username": f"{chosen_role}@example.com", "password": "demo-pass"}
        headers = {"x-request-id": request_id}
        if error_burst and rng.random() < 0.4:
            body["password"] = "wrong-pass"  # nosec B105
    elif spec.name == "reports":
        if error_burst and rng.random() < 0.5:
            params["force_timeout"] = "true"
    elif spec.name == "boom":
        if role_mode == "mixed":
            headers["x-auth-token"] = "demo:admin:admin-bot"

    return path, spec.method, {"params": params, "json": body}, headers


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic traffic for the SDK test app.")
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--duration-seconds", type=int, default=90)
    parser.add_argument("--rps", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--role-mode",
        choices=["viewer", "editor", "admin", "mixed"],
        default="mixed",
    )
    parser.add_argument("--spike-interval-seconds", type=int, default=20)
    parser.add_argument("--spike-multiplier", type=float, default=2.8)
    parser.add_argument("--error-burst-interval-seconds", type=int, default=25)
    parser.add_argument("--error-burst-duration-seconds", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    args = parser.parse_args()

    if args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be > 0")
    if args.rps <= 0:
        raise SystemExit("--rps must be > 0")
    if args.spike_interval_seconds <= 0:
        raise SystemExit("--spike-interval-seconds must be > 0")
    if args.spike_multiplier < 1.0:
        raise SystemExit("--spike-multiplier must be >= 1.0")
    if args.error_burst_interval_seconds <= 0:
        raise SystemExit("--error-burst-interval-seconds must be > 0")
    if args.error_burst_duration_seconds <= 0:
        raise SystemExit("--error-burst-duration-seconds must be > 0")

    signal.signal(signal.SIGINT, _handle_stop_signal)
    signal.signal(signal.SIGTERM, _handle_stop_signal)

    base_url = args.base_url.rstrip("/")
    weighted = _weighted_specs()
    rng = random.Random(args.seed)  # nosec B311 - deterministic fixture traffic
    status_counts: dict[int, int] = {}
    route_counts: dict[str, int] = {}
    failures = 0
    transport_errors = 0
    total_requests = 0
    start_time = time.monotonic()
    end_time = start_time + args.duration_seconds
    tick = 0

    print("synthetic_load: starting")
    print(f"- base_url: {base_url}")
    print(f"- duration_seconds: {args.duration_seconds}")
    print(f"- rps: {args.rps}")
    print(f"- role_mode: {args.role_mode}")
    print(f"- seed: {args.seed}")

    with httpx.Client(timeout=args.timeout_seconds) as client:
        while _KEEP_RUNNING and time.monotonic() < end_time:
            tick += 1
            elapsed_seconds = int(time.monotonic() - start_time)
            in_spike = elapsed_seconds > 0 and elapsed_seconds % args.spike_interval_seconds == 0
            in_error_burst = (
                elapsed_seconds > 0
                and elapsed_seconds % args.error_burst_interval_seconds
                < args.error_burst_duration_seconds
            )
            current_rps = args.rps
            if in_spike:
                current_rps = int(round(args.rps * args.spike_multiplier))
            for req_index in range(current_rps):
                spec = rng.choice(weighted)
                total_requests += 1
                request_id = f"load-{tick:05d}-{req_index:03d}"
                path, method, payload, headers = _request_payload(
                    spec=spec,
                    rng=rng,
                    request_id=request_id,
                    request_index=total_requests,
                    error_burst=in_error_burst,
                    role_mode=args.role_mode,
                )
                route_counts[spec.name] = route_counts.get(spec.name, 0) + 1
                try:
                    response = client.request(
                        method=method,
                        url=f"{base_url}{path}",
                        params=payload["params"],
                        json=payload["json"] or None,
                        headers=headers,
                    )
                except httpx.TransportError as exc:
                    transport_errors += 1
                    failures += 1
                    if transport_errors <= 5 or transport_errors % 25 == 0:
                        print(
                            "transport_error:"
                            f" req={request_id}"
                            f" route={spec.name}"
                            f" error={type(exc).__name__}: {exc}"
                        )
                    continue
                status_counts[response.status_code] = status_counts.get(response.status_code, 0) + 1
                if not response.is_success:
                    failures += 1
            time.sleep(1.0)

    elapsed = round(time.monotonic() - start_time, 2)
    print("synthetic_load: complete")
    print(f"- total_requests: {total_requests}")
    print(f"- non_2xx: {failures}")
    print(f"- transport_errors: {transport_errors}")
    print(f"- elapsed_seconds: {elapsed}")
    print(f"- status_counts: {dict(sorted(status_counts.items()))}")
    print(f"- route_counts: {dict(sorted(route_counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
