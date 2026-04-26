from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from db_reset import truncate_full_schema
from test_alerts import _seed_request_events

from autopulse_backend import jobs


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
