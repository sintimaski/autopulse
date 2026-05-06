from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock


@dataclass(frozen=True, slots=True)
class JobExecutionTelemetry:
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    records_processed: int
    failure_reason: str | None = None


class ServiceMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: Counter[str] = Counter()
        self._gauges: dict[str, int] = {}
        self._job_last_runs: dict[str, JobExecutionTelemetry] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def set_job_last_run(self, telemetry: JobExecutionTelemetry) -> None:
        with self._lock:
            self._job_last_runs[telemetry.job_name] = telemetry

    def set_value(self, name: str, value: int) -> None:
        with self._lock:
            self._gauges[name] = int(value)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {**dict(self._counters), **dict(self._gauges)}

    def job_snapshot(self) -> dict[str, dict[str, int | str | None]]:
        with self._lock:
            return {
                job_name: {
                    **asdict(telemetry),
                    "started_at": telemetry.started_at.astimezone(UTC).isoformat(),
                    "finished_at": telemetry.finished_at.astimezone(UTC).isoformat(),
                }
                for job_name, telemetry in self._job_last_runs.items()
            }


service_metrics = ServiceMetrics()

__all__ = ["JobExecutionTelemetry", "ServiceMetrics", "service_metrics"]
