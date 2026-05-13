"""Optional background job / cron outcome capture (non-blocking).

Canonical location of ``capture_background_job``. The legacy import path
``lumonox._jobs`` re-exports the same symbol so older callers keep working
without modification.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any, Literal

from lumonox.core.runtime_context import get_correlation_id


def capture_background_job(
    app: Any,
    *,
    name: str,
    success: bool,
    latency_ms: float = 0.0,
    trigger: Literal["job", "cron"] = "job",
    correlated_request_id: str | None = None,
    exception: BaseException | None = None,
) -> None:
    """Record a completed background task as a ``type=job`` ingest row (silent if not configured).

    Requires ``monitor()`` / ``lumonox()`` to have been applied on ``app`` so
    ``app.state._lumonox_dispatcher`` exists. Never raises to the caller.
    """
    try:
        dispatcher = getattr(app.state, "_lumonox_dispatcher", None)
        config = getattr(app.state, "_lumonox_config", None)
        if dispatcher is None or config is None:
            return
        raw_name = str(name or "").strip() or "background_task"
        path = raw_name[:2048]
        method = "CRON" if trigger == "cron" else "JOB"
        ok = bool(success) and exception is None
        status_code = 200 if ok else 500
        payload: dict[str, Any] = {
            "type": "job",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "service_name": str(getattr(config, "service_name", "api") or "api")[:120],
            "environment": str(getattr(config, "environment", "production") or "production")[:120],
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": max(0.0, float(latency_ms)),
            "job_trigger": trigger,
        }
        effective_correlation = (
            str(correlated_request_id).strip()[:128]
            if correlated_request_id and str(correlated_request_id).strip()
            else (get_correlation_id() or "").strip()[:128] or None
        )
        if effective_correlation:
            payload["correlated_request_id"] = effective_correlation
            payload["request_id"] = effective_correlation
        if exception is not None:
            payload["exception_type"] = type(exception).__name__
            msg = str(exception).strip()
            if msg:
                payload["exception_message"] = msg[:4000]
            stack = traceback.format_exception(type(exception), exception, exception.__traceback__)
            payload["stack_trace"] = "".join(stack)[-16_000:]
        dispatcher.enqueue(payload)
    except Exception:
        return
