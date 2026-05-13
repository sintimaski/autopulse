"""Event-shape helpers used by every framework adapter.

These functions translate raw timing / exception / infrastructure data into the
dict shape the backend's ``/ingest`` endpoint expects. They are framework-
agnostic — no Starlette / FastAPI imports — so a Django or Flask adapter can
reuse them verbatim.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lumonox.core.config import _MonitorConfig


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _merge_release_git_into_event(config: _MonitorConfig, event: dict[str, Any]) -> None:
    if config.release:
        event["release"] = config.release
    if config.git_sha:
        event["git_sha"] = config.git_sha


def _stable_error_hash(
    exception_type: str, exception_message: str, stack_trace: str, path: str
) -> str:
    # Keep grouping stable across equivalent traces where only line numbers differ.
    # Include route path so the same exception text on different endpoints does not share one hash.
    normalized_stack_trace = re.sub(r"line \d+", "line ?", stack_trace)
    digest = hashlib.sha256()
    digest.update(exception_type.encode("utf-8"))
    digest.update(b"|")
    digest.update(exception_message.encode("utf-8"))
    digest.update(b"|")
    digest.update(normalized_stack_trace.encode("utf-8"))
    digest.update(b"|")
    digest.update((path or "").encode("utf-8"))
    return digest.hexdigest()


def _split_events_for_ingest_json_budget(
    events: list[dict[str, Any]], *, max_bytes: int, sdk_version: str
) -> list[list[dict[str, Any]]]:
    """Split ``events`` so each chunk's JSON body stays under ``max_bytes`` (best-effort).

    If a single event still exceeds ``max_bytes``, it is sent alone so operators see 413s
    instead of silently merging oversized payloads.
    """
    if not events:
        return []
    if max_bytes <= 0:
        return [list(events)]
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for ev in events:
        trial = current + [ev]
        trial_bytes = len(json.dumps({"events": trial, "sdk_version": sdk_version}).encode("utf-8"))
        if trial_bytes <= max_bytes:
            current = trial
            continue
        if current:
            chunks.append(current)
            current = []
        single_bytes = len(json.dumps({"events": [ev], "sdk_version": sdk_version}).encode("utf-8"))
        if single_bytes <= max_bytes:
            current = [ev]
        else:
            chunks.append([ev])
    if current:
        chunks.append(current)
    return chunks


def _build_infrastructure_widget_payload(metrics: Mapping[str, Any]) -> dict[str, Any]:
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
    )
    now = _utc_now_iso()
    definitions: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for source_key, widget_id, title, unit, order in specs:
        raw = metrics.get(source_key)
        if not isinstance(raw, int | float):
            continue
        value = float(raw)
        # psutil uses ..._recv / ..._sent for NIC counters (bytes cumulative since boot).
        if source_key.endswith("_bytes") or source_key in (
            "network_bytes_recv",
            "network_bytes_sent",
        ):
            value = value / (1024 * 1024)
        definitions.append(
            {
                "widget_id": widget_id,
                "type": "line",
                "title": title,
                "description": "Auto-captured infrastructure metric",
                "order": order,
                "config": {"unit": unit},
            }
        )
        points.append({"widget_id": widget_id, "timestamp": now, "value": value})
    return {"definitions": definitions, "points": points}


def _merge_widget_payloads(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    definitions_by_id: dict[str, dict[str, Any]] = {}
    for source in (primary, secondary):
        for item in source.get("definitions", []):
            if isinstance(item, dict) and isinstance(item.get("widget_id"), str):
                definitions_by_id[item["widget_id"]] = item
    points: list[dict[str, Any]] = []
    for source in (primary, secondary):
        for point in source.get("points", []):
            if isinstance(point, dict):
                points.append(point)
    return {"definitions": list(definitions_by_id.values()), "points": points}
