from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from db_reset import truncate_full_schema
from test_alerts import _seed_request_events

from autopulse_backend import jobs
from autopulse_backend.metrics import service_metrics


def test_jobs_cli_alerts_once_prints_zero_with_no_projects(
    backend_test_database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    truncate_full_schema(backend_test_database_url)

    exit_code = jobs.main(["alerts-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "0"


def test_jobs_cli_alerts_once_prints_dispatch_count_after_spike(
    backend_test_database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=25,
        error_count=10,
        base_time=base_time,
    )

    exit_code = jobs.main(["alerts-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "1"


def test_jobs_cli_retention_once_runs(
    backend_test_database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    truncate_full_schema(backend_test_database_url)

    exit_code = jobs.main(["retention-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().isdigit()


def test_jobs_cli_records_last_run_telemetry(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)

    jobs.main(["retention-once"])
    snapshot = service_metrics.job_snapshot()

    assert "retention" in snapshot
    assert snapshot["retention"]["status"] == "succeeded"
    assert isinstance(snapshot["retention"]["duration_ms"], int)


def test_run_retention_sync_runs_on_fresh_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sync_retention.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    from autopulse_backend.jobs import run_retention_sync

    n = run_retention_sync()
    assert isinstance(n, int)
    assert db_path.exists()


def test_retention_once_creates_sqlite_schema_on_fresh_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI must not assume tables exist (cron may run before first API start)."""
    db_path = tmp_path / "fresh_cli.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    exit_code = jobs.main(["retention-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().isdigit()
    assert db_path.exists()
