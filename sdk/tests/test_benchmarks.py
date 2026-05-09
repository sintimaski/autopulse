from __future__ import annotations

from statistics import median
from time import perf_counter

from client_lifespan import lifespan_test_client
from fastapi import FastAPI

from lumonox import monitor

_ITERATIONS = 80
_WARMUP_REQUESTS = 10
_MAX_MEDIAN_OVERHEAD_MS = 6.0
_MAX_P95_OVERHEAD_MS = 10.0


def _build_app(*, with_monitoring: bool) -> FastAPI:
    app = FastAPI()
    if with_monitoring:
        monitor(
            app,
            service_name="benchmark-api",
            environment="benchmark",
            queue_maxsize=512,
            batch_size=50,
            flush_interval_s=5.0,
        )

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


def _measure_request_latencies_ms(app: FastAPI) -> list[float]:
    latencies: list[float] = []
    with lifespan_test_client(app) as client:
        for _ in range(_WARMUP_REQUESTS):
            warmup = client.get("/ping")
            assert warmup.status_code == 200
        for _ in range(_ITERATIONS):
            started = perf_counter()
            response = client.get("/ping")
            elapsed_ms = (perf_counter() - started) * 1000.0
            assert response.status_code == 200
            latencies.append(elapsed_ms)
    return latencies


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    index = int((len(sorted_values) - 1) * percentile)
    return sorted_values[index]


def test_monitoring_hot_path_overhead_stays_within_envelope() -> None:
    baseline_latencies = _measure_request_latencies_ms(_build_app(with_monitoring=False))
    monitored_latencies = _measure_request_latencies_ms(_build_app(with_monitoring=True))

    baseline_sorted = sorted(baseline_latencies)
    monitored_sorted = sorted(monitored_latencies)

    median_overhead = median(monitored_sorted) - median(baseline_sorted)
    p95_overhead = _percentile(monitored_sorted, 0.95) - _percentile(baseline_sorted, 0.95)

    assert median_overhead <= _MAX_MEDIAN_OVERHEAD_MS
    assert p95_overhead <= _MAX_P95_OVERHEAD_MS
