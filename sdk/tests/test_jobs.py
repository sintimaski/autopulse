from __future__ import annotations

from types import SimpleNamespace

from lumonox._jobs import capture_background_job


def test_capture_background_job_is_silent_without_dispatcher() -> None:
    app = SimpleNamespace(state=SimpleNamespace())
    capture_background_job(
        app,
        name="my_task",
        success=False,
        latency_ms=3.0,
        trigger="cron",
        correlated_request_id="rid-1",
        exception=RuntimeError("boom"),
    )


def test_capture_background_job_enqueues_when_dispatcher_present() -> None:
    enqueued: list[dict] = []

    class _Disp:
        def enqueue(self, event: dict) -> None:
            enqueued.append(event)

    app = SimpleNamespace(
        state=SimpleNamespace(
            _lumonox_dispatcher=_Disp(),
            _lumonox_config=SimpleNamespace(service_name="svc", environment="staging"),
        )
    )
    capture_background_job(
        app,
        name="rollups",
        success=True,
        latency_ms=12.5,
        trigger="job",
        correlated_request_id="abc",
    )
    assert len(enqueued) == 1
    ev = enqueued[0]
    assert ev["type"] == "job"
    assert ev["method"] == "JOB"
    assert ev["path"] == "rollups"
    assert ev["status_code"] == 200
    assert ev["request_id"] == "abc"
