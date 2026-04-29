from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None


@dataclass(slots=True)
class InfrastructureSampler:
    ttl_seconds: float = 2.0
    _last_sample: dict[str, Any] = field(default_factory=dict)
    _last_sampled_at: float = 0.0

    def sample(self) -> dict[str, Any]:
        if psutil is None:
            return {}
        now = monotonic()
        if self._last_sample and (now - self._last_sampled_at) < self.ttl_seconds:
            return dict(self._last_sample)

        process = psutil.Process()
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        payload: dict[str, Any] = {
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
            "network_bytes_sent": float(net.bytes_sent),
            "network_bytes_recv": float(net.bytes_recv),
        }
        self._last_sample = payload
        self._last_sampled_at = now
        return dict(payload)
