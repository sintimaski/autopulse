from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from autopulse_backend.config import get_settings
from autopulse_backend.services.event_store import event_store_enabled, try_get_duckdb_event_store

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency
    psutil = None


@dataclass(slots=True)
class InfrastructureMetricsSampler:
    ttl_seconds: float = 2.0
    _last_sample: dict[str, float] = field(default_factory=dict)
    _last_sampled_at: float = 0.0

    def sample(self) -> dict[str, float]:
        if psutil is None:
            return {}
        now = monotonic()
        if self._last_sample and (now - self._last_sampled_at) < self.ttl_seconds:
            return dict(self._last_sample)
        process = psutil.Process()
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()
        net = psutil.net_io_counters()
        sample: dict[str, float] = {
            "host_cpu_percent": float(psutil.cpu_percent(interval=None)),
            "host_memory_used_percent": float(vm.percent),
            "host_memory_total_bytes": float(vm.total),
            "host_memory_used_bytes": float(vm.used),
            "process_cpu_percent": float(process.cpu_percent(interval=None)),
            "process_memory_percent": float(process.memory_percent()),
            "process_memory_rss_bytes": float(process.memory_info().rss),
            "disk_used_percent": float(disk.percent),
            "disk_total_bytes": float(disk.total),
            "disk_used_bytes": float(disk.used),
            "disk_io_read_bytes": float(disk_io.read_bytes if disk_io is not None else 0.0),
            "disk_io_write_bytes": float(disk_io.write_bytes if disk_io is not None else 0.0),
            "network_bytes_sent": float(net.bytes_sent),
            "network_bytes_recv": float(net.bytes_recv),
        }
        settings = get_settings()
        if event_store_enabled(settings):
            store = try_get_duckdb_event_store()
            if store is not None:
                size_bytes = float(store.file_size_bytes())
                sample["embedded_log_store_size_bytes"] = size_bytes
                sample["embedded_log_store_size_mb"] = size_bytes / (1024 * 1024)
                if settings.embedded_sqlite_max_db_file_mb is not None:
                    cap_mb = float(settings.embedded_sqlite_max_db_file_mb)
                    sample["embedded_log_store_cap_mb"] = cap_mb
                    if cap_mb > 0:
                        sample["embedded_log_store_usage_percent"] = (
                            (size_bytes / (1024 * 1024)) / cap_mb
                        ) * 100.0
        self._last_sample = sample
        self._last_sampled_at = now
        return dict(sample)


def to_widget_payload(metrics: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    specs: tuple[tuple[str, str, str, str, int], ...] = (
        ("host_cpu_percent", "infra_host_cpu_percent", "Host CPU", "%", 500),
        ("host_memory_used_percent", "infra_host_memory_percent", "Host memory used", "%", 510),
        ("process_cpu_percent", "infra_process_cpu_percent", "App CPU", "%", 520),
        ("process_memory_percent", "infra_process_memory_percent", "App memory share", "%", 530),
        ("process_memory_rss_bytes", "infra_process_memory_rss_mb", "App RSS memory", "MB", 540),
        ("disk_used_percent", "infra_disk_used_percent", "Host disk used", "%", 550),
        ("disk_io_read_bytes", "infra_disk_io_read_mb", "Disk I/O read", "MB", 552),
        ("disk_io_write_bytes", "infra_disk_io_write_mb", "Disk I/O write", "MB", 553),
        ("network_bytes_recv", "infra_network_received_mb", "Network received", "MB", 560),
        ("network_bytes_sent", "infra_network_sent_mb", "Network sent", "MB", 570),
        (
            "embedded_log_store_size_mb",
            "infra_embedded_log_store_size_mb",
            "Embedded log store size",
            "MB",
            580,
        ),
        (
            "embedded_log_store_usage_percent",
            "infra_embedded_log_store_usage_percent",
            "Embedded log store usage",
            "%",
            581,
        ),
    )
    definitions: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for source_key, widget_id, title, unit, order in specs:
        raw_value = metrics.get(source_key)
        if not isinstance(raw_value, int | float):
            continue
        value = float(raw_value)
        if source_key.endswith("_bytes"):
            value = value / (1024 * 1024)
        definitions.append(
            {
                "widget_id": widget_id,
                "widget_type": "line",
                "title": title,
                "description": "AutoPulse host/app infrastructure metric",
                "display_order": order,
                "config": {"unit": unit},
            }
        )
        points.append({"widget_id": widget_id, "value": value})
    return definitions, points
