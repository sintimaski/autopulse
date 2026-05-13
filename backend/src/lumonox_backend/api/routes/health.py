from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from lumonox_backend.core.config import get_settings, scheduler_required_for_env
from lumonox_backend.database import get_engine, get_session_maker
from lumonox_backend.metrics import service_metrics
from lumonox_backend.repositories import ingest_reliability as ingest_reliability_repo
from lumonox_backend.services.duckdb_async import run_duckdb_read_sync
from lumonox_backend.services.event_store import (
    event_store_enabled,
    try_get_duckdb_event_store,
)

router = APIRouter(tags=["system"])
_REPLAY_QUEUE_STALE_PENDING_SECONDS = 600

# Alerts subsystem flips to degraded only once outbound webhook counters cross
# these per-process thresholds. A single send failure or validation rejection is
# noted in the summary text but does not degrade the row — many real-world
# transient failures (DNS blip, single 503) clear themselves before the next
# alerts tick and would otherwise produce a misleading degraded signal.
ALERTS_WEBHOOK_SEND_FAILED_DEGRADED_THRESHOLD = 5
ALERTS_WEBHOOK_VALIDATION_REJECTED_DEGRADED_THRESHOLD = 10


def _scheduler_running(scheduler: object) -> bool:
    tasks = getattr(scheduler, "tasks", None)
    return bool(
        scheduler is not None
        and isinstance(tasks, list)
        and any(isinstance(task, asyncio.Task) and not task.done() for task in tasks)
    )


def _topology_guardrail_status(
    *,
    lumonox_env: str,
    database_url: str,
    database_run_migrations_on_startup: bool,
    scheduler_running: bool,
    jobs_enable_scheduler: bool,
    scheduler_required: bool,
    jobs_external_cron_ownership: bool = False,
    dashboard_realtime_bus_backend: str,
) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    if scheduler_required and not jobs_enable_scheduler:
        findings.append(
            {
                "severity": "unsafe",
                "code": "scheduler-required-env-without-in-process-scheduler",
                "message": (
                    "set JOBS_ENABLE_SCHEDULER=true or document external cron ownership "
                    "(JOBS_EXTERNAL_CRON_OWNERSHIP=true)"
                ),
            }
        )
    elif scheduler_required and not scheduler_running:
        findings.append(
            {
                "severity": "risky",
                "code": "scheduler-required-env-scheduler-not-running",
                "message": (
                    "scheduler is required for this environment but no scheduler tasks are running"
                ),
            }
        )
    env = (lumonox_env or "development").strip().lower()
    if env in {"staging", "production"} and dashboard_realtime_bus_backend == "none":
        findings.append(
            {
                "severity": "risky",
                "code": "realtime-bus-none",
                "message": (
                    "multi-instance deployments must validate websocket stickiness "
                    "or dedicated ws routing when DASHBOARD_REALTIME_BUS_BACKEND=none"
                ),
            }
        )
    if (
        env in {"staging", "production"}
        and not database_url.startswith("sqlite")
        and database_run_migrations_on_startup
    ):
        findings.append(
            {
                "severity": "risky",
                "code": "non-sql-startup-migrations-enabled",
                "message": (
                    "DATABASE_RUN_MIGRATIONS_ON_STARTUP=true with non-SQLite metadata DB; "
                    "prefer one-shot migrations before rollout and set startup migrations false "
                    "on steady-state replicas"
                ),
            }
        )
    if jobs_external_cron_ownership and jobs_enable_scheduler:
        findings.append(
            {
                "severity": "non-ideal",
                "code": "external-cron-ownership-with-in-process-scheduler-enabled",
                "message": (
                    "JOBS_EXTERNAL_CRON_OWNERSHIP=true while JOBS_ENABLE_SCHEDULER=true; "
                    "prefer one scheduler owner model per environment"
                ),
            }
        )
    unsafe_count = sum(1 for finding in findings if finding["severity"] == "unsafe")
    risky_count = sum(1 for finding in findings if finding["severity"] == "risky")
    non_ideal_count = sum(1 for finding in findings if finding["severity"] == "non-ideal")
    has_blocking_findings = unsafe_count > 0 or risky_count > 0
    status = "healthy" if not has_blocking_findings else "degraded"
    reasons = [f"{finding['severity']}:{finding['code']}" for finding in findings]
    return {
        "status": status,
        "scheduler_required": scheduler_required,
        "unsafe_count": unsafe_count,
        "risky_count": risky_count,
        "non_ideal_count": non_ideal_count,
        "reasons": reasons,
        "findings": findings,
    }


def _require_internal_metrics_access(request: Request) -> None:
    settings = get_settings()
    expected = settings.internal_metrics_bearer_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Metrics endpoint is disabled (set INTERNAL_METRICS_BEARER_TOKEN).",
        )
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized metrics access",
        )


def _build_ingest_pressure_view(counters: dict[str, int]) -> dict[str, object]:
    """Summarize ingest backpressure signals operators should watch.

    Thresholds (defaults; tune with real traffic):
    - ``rate_limited_total`` > 0 while ``accepted_batches`` is flat: SDK hot loop
      or client mis-tuning; verify `INGEST_RATE_LIMIT_*`.
    - ``payload_too_large_total`` > 0: SDK batching too aggressively; check SDK
      ``batch_size_max_events`` and body scrubbing.
    - ``aggregate_worker_sync_fallback_total`` > 0: async worker queue saturated;
      ingest still served, but the async path is not keeping up.
    - ``aggregate_worker_failed_total`` > 0: inspect logs for the accompanying
      ``ingest_aggregate_worker_failed`` exception traceback.
    - ``persist_sql_tail_failed_total`` > 0: SQL tail failed after DuckDB writes; verify DB health.
      See ops docs on cross-store consistency.
    - ``sql_tail_repair_dead_lettered_total`` > 0: replay queue exhausted retries;
      investigate oldest failed payload and run replay CLI after remediation.
    """
    accepted_batches = int(counters.get("ingest.accepted.batches", 0))
    accepted_events = int(counters.get("ingest.accepted.events", 0))
    rate_limited = int(counters.get("ingest.rejected.rate_limited", 0))
    batch_too_large = int(counters.get("ingest.rejected.batch_too_large", 0))
    payload_too_large_header = int(counters.get("ingest.rejected.payload_too_large", 0))
    payload_too_large_stream = int(counters.get("ingest.rejected.payload_too_large_stream", 0))
    non_https = int(counters.get("ingest.rejected.non_https", 0))
    distributed_fallback = int(counters.get("ingest.rate_limit.distributed_fallback", 0))
    enqueue_failed = int(counters.get("ingest.aggregate_worker.enqueue_failed", 0))
    queue_full = int(counters.get("ingest.aggregate_worker.queue_full", 0))
    sync_fallback = int(counters.get("ingest.aggregate_worker.sync_fallback", 0))
    worker_succeeded = int(counters.get("ingest.aggregate_worker.succeeded", 0))
    worker_failed = int(counters.get("ingest.aggregate_worker.failed", 0))
    persist_sql_tail_failed = int(counters.get("ingest.persist_sql_tail_failed", 0))
    sql_tail_repair_queued = int(counters.get("ingest.sql_tail.repair_queued", 0))
    sql_tail_repair_enqueue_failed = int(counters.get("ingest.sql_tail.repair_enqueue_failed", 0))
    sql_tail_repair_succeeded = int(counters.get("ingest.sql_tail.repair_succeeded", 0))
    sql_tail_repair_failed = int(counters.get("ingest.sql_tail.repair_failed", 0))
    sql_tail_repair_dead_lettered = int(counters.get("ingest.sql_tail.repair_dead_lettered", 0))
    realtime_fanout_scheduled = int(counters.get("ingest.realtime_fanout.scheduled", 0))
    realtime_fanout_succeeded = int(counters.get("ingest.realtime_fanout.succeeded", 0))
    realtime_fanout_failed = int(counters.get("ingest.realtime_fanout.failed", 0))
    realtime_fanout_cancelled = int(counters.get("ingest.realtime_fanout.cancelled", 0))
    realtime_fanout_pending = int(counters.get("ingest.realtime_fanout.pending_tasks", 0))
    replay_queue_pending = int(counters.get("ingest.replay_queue.pending_sql_tail_repairs", 0))
    replay_queue_dead_lettered = int(
        counters.get("ingest.replay_queue.dead_lettered_sql_tail_repairs", 0)
    )
    replay_queue_aggregate_dead_letter_backlog = int(
        counters.get("ingest.replay_queue.aggregate_dead_letter_backlog", 0)
    )
    replay_queue_oldest_pending_age_seconds = int(
        counters.get("ingest.replay_queue.oldest_pending_age_seconds", 0)
    )
    event_plane_append_rejected = int(counters.get("event_plane.shards.append_rejected_total", 0))
    event_plane_append_failed = int(counters.get("event_plane.shards.append_failed_total", 0))
    return {
        "accepted_batches_total": accepted_batches,
        "accepted_events_total": accepted_events,
        "rate_limited_total": rate_limited,
        "batch_too_large_total": batch_too_large,
        "payload_too_large_total": payload_too_large_header + payload_too_large_stream,
        "payload_too_large_header_total": payload_too_large_header,
        "payload_too_large_stream_total": payload_too_large_stream,
        "non_https_rejected_total": non_https,
        "distributed_rate_limit_fallback_total": distributed_fallback,
        "aggregate_worker_enqueue_failed_total": enqueue_failed,
        "aggregate_worker_queue_full_total": queue_full,
        "aggregate_worker_sync_fallback_total": sync_fallback,
        "aggregate_worker_succeeded_total": worker_succeeded,
        "aggregate_worker_failed_total": worker_failed,
        "persist_sql_tail_failed_total": persist_sql_tail_failed,
        "sql_tail_repair_queued_total": sql_tail_repair_queued,
        "sql_tail_repair_enqueue_failed_total": sql_tail_repair_enqueue_failed,
        "sql_tail_repair_succeeded_total": sql_tail_repair_succeeded,
        "sql_tail_repair_failed_total": sql_tail_repair_failed,
        "sql_tail_repair_dead_lettered_total": sql_tail_repair_dead_lettered,
        "realtime_fanout_scheduled_total": realtime_fanout_scheduled,
        "realtime_fanout_succeeded_total": realtime_fanout_succeeded,
        "realtime_fanout_failed_total": realtime_fanout_failed,
        "realtime_fanout_cancelled_total": realtime_fanout_cancelled,
        "realtime_fanout_pending_tasks": realtime_fanout_pending,
        "replay_queue_pending_sql_tail_repairs": replay_queue_pending,
        "replay_queue_dead_lettered_sql_tail_repairs": replay_queue_dead_lettered,
        "replay_queue_aggregate_dead_letter_backlog": replay_queue_aggregate_dead_letter_backlog,
        "replay_queue_oldest_pending_age_seconds": replay_queue_oldest_pending_age_seconds,
        "event_plane_append_rejected_total": event_plane_append_rejected,
        "event_plane_append_failed_total": event_plane_append_failed,
    }


async def _build_replay_queue_readiness(database_url: str) -> dict[str, object]:
    session_maker = get_session_maker(database_url)
    async with session_maker() as session:
        queue_health = await ingest_reliability_repo.fetch_replay_queue_health(session)
    reasons: list[str] = []
    if queue_health.dead_lettered_sql_tail_repairs > 0:
        reasons.append("dead_lettered_sql_tail_repairs_present")
    if queue_health.aggregate_dead_letter_backlog > 0:
        reasons.append("aggregate_dead_letter_backlog_present")
    if (
        queue_health.pending_sql_tail_repairs > 0
        and queue_health.oldest_pending_age_seconds >= _REPLAY_QUEUE_STALE_PENDING_SECONDS
    ):
        reasons.append("sql_tail_repair_pending_stale")
    status_label = "degraded" if reasons else "healthy"
    return {
        "status": status_label,
        "reasons": reasons,
        "pending_sql_tail_repairs": queue_health.pending_sql_tail_repairs,
        "dead_lettered_sql_tail_repairs": queue_health.dead_lettered_sql_tail_repairs,
        "aggregate_dead_letter_backlog": queue_health.aggregate_dead_letter_backlog,
        "oldest_pending_age_seconds": queue_health.oldest_pending_age_seconds,
        "stale_pending_threshold_seconds": _REPLAY_QUEUE_STALE_PENDING_SECONDS,
    }


def _build_metrics_snapshot(request: Request) -> dict[str, object]:
    settings = get_settings()
    scheduler = getattr(request.app.state, "_lumonox_scheduler", None)
    pressure = getattr(request.app.state, "_lumonox_retention_pressure_poll", None)
    tick_task = getattr(request.app.state, "_lumonox_dashboard_ws_tick_task", None)
    aggregate_worker = getattr(request.app.state, "_lumonox_ingest_aggregate_worker", None)
    realtime_bus_task = getattr(request.app.state, "_lumonox_realtime_bus_subscriber_task", None)
    dashboard_ws_tick_running = isinstance(tick_task, asyncio.Task) and not tick_task.done()
    realtime_bus_subscriber_running = (
        isinstance(realtime_bus_task, asyncio.Task) and not realtime_bus_task.done()
    )
    scheduler_running = _scheduler_running(scheduler)
    topology_guardrails = _topology_guardrail_status(
        lumonox_env=settings.lumonox_env,
        database_url=settings.database_url,
        database_run_migrations_on_startup=settings.database_run_migrations_on_startup,
        scheduler_running=scheduler_running,
        jobs_enable_scheduler=settings.jobs_enable_scheduler,
        scheduler_required=scheduler_required_for_env(settings),
        jobs_external_cron_ownership=settings.jobs_external_cron_ownership,
        dashboard_realtime_bus_backend=settings.dashboard_realtime_bus_backend,
    )
    retention_pressure_poll_running = bool(
        pressure is not None
        and isinstance(getattr(pressure, "task", None), asyncio.Task)
        and not pressure.task.done()
    )
    duckdb_metrics: dict[str, object] = {}
    if event_store_enabled(settings):
        store = try_get_duckdb_event_store()
        if store is not None:
            size_bytes = int(store.file_size_bytes())
            cap_mb = settings.sqlite_max_db_file_mb
            duckdb_metrics = {
                "path": settings.event_store_duckdb_path,
                "file_size_bytes": size_bytes,
                "file_size_mb": round(size_bytes / (1024 * 1024), 3),
                "max_size_mb": int(cap_mb) if cap_mb is not None else None,
                "usage_ratio": (
                    float(size_bytes) / float(int(cap_mb) * 1024 * 1024)
                    if cap_mb is not None and int(cap_mb) > 0
                    else None
                ),
            }
    counters = service_metrics.snapshot()
    aggregate_queue_depth: int | None = None
    aggregate_queue_max_size: int | None = None
    fanout_tasks_pending = 0
    try:
        if aggregate_worker is not None and hasattr(aggregate_worker, "queue"):
            aggregate_queue_depth = aggregate_worker.queue.qsize()
            max_size = aggregate_worker.queue.maxsize
            aggregate_queue_max_size = int(max_size) if max_size else None
        fanout_tasks: object = getattr(request.app.state, "_lumonox_ingest_fanout_tasks", set())
        if isinstance(fanout_tasks, set):
            fanout_tasks_pending = len([task for task in fanout_tasks if not task.done()])
    except Exception:  # noqa: BLE001 - best-effort telemetry
        aggregate_queue_depth = None
        fanout_tasks_pending = 0
    return {
        "service": "lumonox",
        "lumonox_env": settings.lumonox_env,
        "event_plane_mode": settings.event_plane_mode,
        "dashboard_auth_enabled": settings.dashboard_auth_enabled,
        "dashboard_ws_live_tick_seconds": settings.dashboard_ws_live_tick_seconds,
        "dashboard_ws_tick_running": dashboard_ws_tick_running,
        "dashboard_realtime_bus_backend": settings.dashboard_realtime_bus_backend,
        "dashboard_realtime_bus_channel": settings.dashboard_realtime_bus_channel,
        "dashboard_realtime_bus_subscriber_running": realtime_bus_subscriber_running,
        "scheduler_running": scheduler_running,
        "retention_pressure_poll_running": retention_pressure_poll_running,
        "jobs_enable_scheduler": settings.jobs_enable_scheduler,
        "jobs_external_cron_ownership": settings.jobs_external_cron_ownership,
        "retention_pressure_poll_seconds": settings.retention_pressure_poll_seconds,
        "jobs_retention_interval_seconds": settings.jobs_retention_interval_seconds,
        "event_store": settings.event_store,
        "duckdb": duckdb_metrics if duckdb_metrics else None,
        "counters": counters,
        "jobs": service_metrics.job_snapshot(),
        "topology_profile": {
            "event_store": settings.event_store,
            "event_plane_mode": settings.event_plane_mode,
            "duckdb_single_writer_profile": settings.event_store_duckdb_single_writer_profile,
            "jobs_enable_scheduler": settings.jobs_enable_scheduler,
            "jobs_external_cron_ownership": settings.jobs_external_cron_ownership,
            "dashboard_auth_enabled": settings.dashboard_auth_enabled,
            "dashboard_realtime_bus_backend": settings.dashboard_realtime_bus_backend,
        },
        "topology_guardrails": topology_guardrails,
        "ingest_pressure": _build_ingest_pressure_view(counters),
        "ingest_aggregate_queue": {
            "enabled": settings.ingest_async_aggregate_enabled,
            "depth": aggregate_queue_depth,
            "max_size": aggregate_queue_max_size,
        },
        "ingest_realtime_fanout": {
            "pending_tasks": fanout_tasks_pending,
        },
        "parquet_export": {
            "enabled": settings.parquet_export_enabled,
            "interval_seconds": settings.parquet_export_interval_seconds,
            "window_seconds": settings.parquet_export_window_seconds,
            "root": settings.parquet_export_root,
            "query_enabled": settings.parquet_query_enabled,
            "hot_window_hours": settings.parquet_hot_window_hours,
            "lifecycle_enabled": settings.parquet_lifecycle_enabled,
            "lifecycle_interval_seconds": settings.parquet_lifecycle_interval_seconds,
            "lifecycle_retention_days": settings.parquet_lifecycle_retention_days,
            "lifecycle_dry_run": settings.parquet_lifecycle_dry_run,
            "object_storage_enabled": settings.parquet_object_storage_enabled,
            "object_storage_interval_seconds": settings.parquet_object_storage_interval_seconds,
            "object_storage_uri": settings.parquet_object_storage_uri,
            "object_storage_prefix": settings.parquet_object_storage_prefix,
            "object_storage_verify_upload": settings.parquet_object_storage_verify_upload,
            "object_storage_restore_root": settings.parquet_object_storage_restore_root,
        },
    }


_STATUS_RANK = ("critical", "degraded", "unknown", "not_configured", "healthy")


def _rank_status(status: str) -> int:
    try:
        return _STATUS_RANK.index(status)
    except ValueError:
        return len(_STATUS_RANK)


def _pick_worse(a: str, b: str) -> str:
    return a if _rank_status(a) <= _rank_status(b) else b


def build_operator_health_subsystems(snapshot: dict[str, object]) -> dict[str, object]:
    """Derive a compact operator-facing health matrix from an internal metrics snapshot.

    Status semantics align with the dashboard: ``healthy``, ``degraded``, ``critical``,
    ``unknown`` (insufficient signal), and ``not_configured`` (subsystem intentionally off).
    """
    subsystems: list[dict[str, str | None]] = []
    overall = "healthy"

    tg_raw = snapshot.get("topology_guardrails")
    tg = tg_raw if isinstance(tg_raw, dict) else {}
    unsafe = int(tg.get("unsafe_count") or 0)
    risky = int(tg.get("risky_count") or 0)
    non_ideal = int(tg.get("non_ideal_count") or 0)
    tg_status = str(tg.get("status") or "unknown")
    if unsafe > 0:
        topo_status: str = "critical"
    elif risky > 0 or tg_status != "healthy" or non_ideal > 0:
        topo_status = "degraded"
    else:
        topo_status = "healthy"
    topo_summary = (
        f"{unsafe} unsafe, {risky} risky, {non_ideal} non-ideal topology signals"
        if (unsafe or risky or non_ideal)
        else "No blocking topology guardrail findings on this process."
    )
    subsystems.append(
        {
            "id": "topology",
            "label": "Topology guardrails",
            "status": topo_status,
            "summary": topo_summary,
            "settings_anchor": "lx-settings-system-diagnostics",
        }
    )
    overall = _pick_worse(overall, topo_status)

    jobs_enable = bool(snapshot.get("jobs_enable_scheduler"))
    scheduler_running = bool(snapshot.get("scheduler_running"))
    if not jobs_enable:
        sched_status = "not_configured"
        sched_summary = "In-process scheduler disabled (`JOBS_ENABLE_SCHEDULER=false`)."
    elif scheduler_running:
        sched_status = "healthy"
        sched_summary = "Scheduler task loop is running on this worker."
    else:
        sched_status = "critical"
        sched_summary = "Scheduler enabled but no active scheduler tasks observed on this worker."
    subsystems.append(
        {
            "id": "scheduler",
            "label": "Scheduler",
            "status": sched_status,
            "summary": sched_summary,
            "settings_anchor": "lx-settings-internal-metrics",
        }
    )
    overall = _pick_worse(overall, sched_status)

    pressure_raw = snapshot.get("ingest_pressure")
    pressure = pressure_raw if isinstance(pressure_raw, dict) else {}
    worker_failed = int(pressure.get("aggregate_worker_failed_total") or 0)
    dead_letter = int(pressure.get("sql_tail_repair_dead_lettered_total") or 0)
    plane_failed = int(pressure.get("event_plane_append_failed_total") or 0)
    persist_failed = int(pressure.get("persist_sql_tail_failed_total") or 0)
    payload_large = int(pressure.get("payload_too_large_total") or 0)
    rate_limited = int(pressure.get("rate_limited_total") or 0)
    sync_fb = int(pressure.get("aggregate_worker_sync_fallback_total") or 0)
    if worker_failed or dead_letter or plane_failed:
        ingest_status = "critical"
        ingest_summary = (
            f"Ingest pipeline errors: worker_failed={worker_failed}, "
            f"sql_tail_dead_lettered={dead_letter}, event_plane_failed={plane_failed}."
        )
    elif persist_failed or sync_fb:
        ingest_status = "degraded"
        ingest_summary = (
            f"Pressure signals: persist_sql_tail_failed={persist_failed}, "
            f"aggregate_sync_fallback={sync_fb}, rate_limited={rate_limited}."
        )
    elif payload_large or rate_limited > 0:
        ingest_status = "degraded"
        ingest_summary = (
            f"Clients hitting limits: payload_too_large={payload_large}, "
            f"rate_limited_batches={rate_limited}."
        )
    else:
        ingest_status = "healthy"
        ingest_summary = "No elevated ingest rejection or worker failure counters on this process."
    subsystems.append(
        {
            "id": "ingest",
            "label": "Ingest + aggregate pipeline",
            "status": ingest_status,
            "summary": ingest_summary,
            "settings_anchor": "lx-settings-internal-metrics",
        }
    )
    overall = _pick_worse(overall, ingest_status)

    bus_backend = str(snapshot.get("dashboard_realtime_bus_backend") or "none").strip().lower()
    bus_running = bool(snapshot.get("dashboard_realtime_bus_subscriber_running"))
    lumonox_env = str(snapshot.get("lumonox_env") or "development").strip().lower()
    if bus_backend in {"", "none"}:
        if lumonox_env in {"staging", "production"}:
            rt_status = "degraded"
            rt_summary = (
                "Realtime bus backend is `none`; multi-replica live dashboards need sticky WS "
                "sessions or `DASHBOARD_REALTIME_BUS_BACKEND=postgres_notify` on Postgres."
            )
        else:
            rt_status = "healthy"
            rt_summary = "Realtime bus backend is `none` (typical for single-process development)."
    elif bus_backend == "postgres_notify" and not bus_running:
        rt_status = "degraded"
        rt_summary = (
            "Postgres notify bus configured but subscriber task is not running on this worker."
        )
    else:
        rt_status = "healthy"
        rt_summary = f"Realtime bus backend `{bus_backend}` reports healthy subscriber state."
    subsystems.append(
        {
            "id": "realtime",
            "label": "Dashboard realtime bus",
            "status": rt_status,
            "summary": rt_summary,
            "settings_anchor": "lx-settings-system-diagnostics",
        }
    )
    overall = _pick_worse(overall, rt_status)

    retention_running = bool(snapshot.get("retention_pressure_poll_running"))
    if jobs_enable:
        ret_status = "healthy" if retention_running else "degraded"
        ret_summary = (
            "Retention pressure poll task is running."
            if retention_running
            else "Scheduler enabled but retention pressure poll is not running on this worker."
        )
    else:
        ret_status = "not_configured"
        ret_summary = "Scheduler off; retention poll not expected on this process."
    subsystems.append(
        {
            "id": "retention_poll",
            "label": "Retention pressure poll",
            "status": ret_status,
            "summary": ret_summary,
            "settings_anchor": "lx-settings-internal-metrics",
        }
    )
    overall = _pick_worse(overall, ret_status)

    jobs_raw = snapshot.get("jobs")
    jobs = jobs_raw if isinstance(jobs_raw, dict) else {}
    alerts_telemetry = jobs.get("alerts")
    counters_raw = snapshot.get("counters")
    counters = counters_raw if isinstance(counters_raw, dict) else {}
    webhook_send_failed = int(counters.get("alerts.webhook.send.failed", 0) or 0)
    webhook_url_rejected = int(counters.get("alerts.webhook.validation_rejected", 0) or 0)
    if not isinstance(alerts_telemetry, dict):
        alert_status = "unknown"
        alert_summary = "No recent `alerts` job telemetry on this process yet."
    else:
        alert_state = str(alerts_telemetry.get("status") or "unknown").lower()
        if alert_state == "failed":
            alert_status = "degraded"
            reason = alerts_telemetry.get("failure_reason") or "unknown"
            alert_summary = (
                f"Last alerts job run failed ({reason}). Check SMTP/webhook settings and logs."
            )
        elif alert_state in {"succeeded", "started"}:
            alert_status = "healthy"
            alert_summary = f"Last alerts job status: {alert_state}."
        else:
            alert_status = "unknown"
            alert_summary = f"Alerts job in state `{alert_state}`."
    if webhook_send_failed > 0 or webhook_url_rejected > 0:
        extra = (
            f" Outbound webhook telemetry on this process: "
            f"send_failed={webhook_send_failed}, url_validation_rejected={webhook_url_rejected}."
        )
        if (
            webhook_send_failed >= ALERTS_WEBHOOK_SEND_FAILED_DEGRADED_THRESHOLD
            or webhook_url_rejected >= ALERTS_WEBHOOK_VALIDATION_REJECTED_DEGRADED_THRESHOLD
        ) and alert_status in {"healthy", "unknown"}:
            alert_status = "degraded"
        alert_summary = f"{alert_summary.rstrip('.')}.{extra}"
    subsystems.append(
        {
            "id": "alerts",
            "label": "Alert delivery job",
            "status": alert_status,
            "summary": alert_summary,
            "settings_anchor": "lx-settings-system-diagnostics",
        }
    )
    overall = _pick_worse(overall, alert_status)

    return {"overall_status": overall, "subsystems": subsystems}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse | dict[str, object]:
    settings = get_settings()
    scheduler = getattr(request.app.state, "_lumonox_scheduler", None)
    scheduler_running = _scheduler_running(scheduler)
    engine = get_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready",
        ) from exc
    if event_store_enabled(settings):
        store = try_get_duckdb_event_store()
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DuckDB event store not ready",
            )
        try:
            await run_duckdb_read_sync(store.ping_sync, duckdb_read_operation="health_ping")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DuckDB event store ping failed",
            ) from exc
    topology_guardrails = _topology_guardrail_status(
        lumonox_env=settings.lumonox_env,
        database_url=settings.database_url,
        database_run_migrations_on_startup=settings.database_run_migrations_on_startup,
        scheduler_running=scheduler_running,
        jobs_enable_scheduler=settings.jobs_enable_scheduler,
        scheduler_required=scheduler_required_for_env(settings),
        jobs_external_cron_ownership=settings.jobs_external_cron_ownership,
        dashboard_realtime_bus_backend=settings.dashboard_realtime_bus_backend,
    )
    replay_queue_readiness = await _build_replay_queue_readiness(settings.database_url)
    payload = {
        "lumonox_env": settings.lumonox_env,
        "event_plane_mode": settings.event_plane_mode,
        "dashboard_auth_enabled": settings.dashboard_auth_enabled,
        "jobs_enable_scheduler": settings.jobs_enable_scheduler,
        "jobs_external_cron_ownership": settings.jobs_external_cron_ownership,
        "scheduler_running": scheduler_running,
        "database_run_migrations_on_startup": settings.database_run_migrations_on_startup,
        "dashboard_realtime_bus_backend": settings.dashboard_realtime_bus_backend,
        "topology_guardrails": topology_guardrails,
        "replay_queue_readiness": replay_queue_readiness,
    }
    if topology_guardrails["status"] != "healthy" or replay_queue_readiness["status"] != "healthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", **payload},
        )
    return {"status": "ready", **payload}


@router.get("/internal/metrics")
async def internal_metrics(request: Request) -> dict[str, object]:
    _require_internal_metrics_access(request)
    return _build_metrics_snapshot(request)


@router.get("/metrics")
async def prometheus_metrics(request: Request) -> Response:
    _require_internal_metrics_access(request)
    snapshot = _build_metrics_snapshot(request)
    counters = snapshot.get("counters", {})
    jobs = snapshot.get("jobs", {})
    pressure = snapshot.get("ingest_pressure", {})
    aggregate_queue = snapshot.get("ingest_aggregate_queue", {})
    lines = [
        "# TYPE lumonox_scheduler_running gauge",
        f"lumonox_scheduler_running {1 if snapshot.get('scheduler_running') else 0}",
    ]
    if isinstance(counters, dict):
        for name, value in counters.items():
            metric_name = f"lumonox_{str(name).replace('.', '_')}"
            try:
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {int(value)}")
            except (TypeError, ValueError):
                continue
    if isinstance(jobs, dict):
        for job_name, telemetry in jobs.items():
            if not isinstance(telemetry, dict):
                continue
            metric_name = f"lumonox_job_{job_name}_last_duration_ms"
            lines.append(f"# TYPE {metric_name} gauge")
            duration = telemetry.get("duration_ms", 0)
            try:
                lines.append(f"{metric_name} {int(duration)}")
            except (TypeError, ValueError):
                lines.append(f"{metric_name} 0")
    if isinstance(pressure, dict):
        for name, value in pressure.items():
            metric_name = f"lumonox_ingest_pressure_{name}"
            try:
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name} {int(value)}")
            except (TypeError, ValueError):
                continue
    if isinstance(aggregate_queue, dict):
        depth = aggregate_queue.get("depth")
        max_size = aggregate_queue.get("max_size")
        if isinstance(depth, int):
            lines.append("# TYPE lumonox_ingest_aggregate_queue_depth gauge")
            lines.append(f"lumonox_ingest_aggregate_queue_depth {depth}")
        if isinstance(max_size, int) and max_size > 0:
            lines.append("# TYPE lumonox_ingest_aggregate_queue_max_size gauge")
            lines.append(f"lumonox_ingest_aggregate_queue_max_size {max_size}")
    lines.append("")
    return Response(content="\n".join(lines), media_type="text/plain; version=0.0.4")
