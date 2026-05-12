from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from db_reset import truncate_full_schema
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.alerts import (
    AlertDeliveryResult,
    AlertSignal,
    EmailAlertSender,
    StubAlertSender,
    evaluate_alerts_once,
)
from lumonox_backend.core.config import get_settings
from lumonox_backend.models import Event, Project
from lumonox_backend.repositories.alert_settings import get_or_create_project_alert_settings


@pytest.fixture(autouse=True)
def _sqlite_event_store_for_alert_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests seed the SQL ``events`` table; DuckDB-backed reads would return zero counts."""
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "sqlite")


def _seed_request_events(
    database_url: str,
    *,
    request_count: int,
    error_count: int,
    base_time: datetime,
) -> str:
    async def run() -> str:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Alert Test Project")
                session.add(project)
                await session.flush()
                for index in range(request_count):
                    is_error = index < error_count
                    event_time = base_time + timedelta(seconds=index)
                    session.add(
                        Event(
                            project_id=project.id,
                            timestamp=event_time,
                            received_at=event_time,
                            sdk_version="0.1.0",
                            type="request",
                            service_name="api",
                            environment="test",
                            method="GET",
                            path="/work",
                            status_code=500 if is_error else 200,
                            latency_ms=20.0,
                            payload={"type": "request"},
                            request_id=f"req-{index}",
                        )
                    )
                await session.commit()
                return str(project.id)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _run_alert_job(
    database_url: str,
    *,
    now: datetime,
    error_spike_min_requests: int,
    error_spike_ratio_threshold: float,
    outage_min_requests: int,
    cooldown_minutes: int,
    alerts_enabled: bool = True,
) -> tuple[int, int]:
    async def run() -> tuple[int, int]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        sender = StubAlertSender()
        try:
            async with session_maker() as session:
                base_settings = get_settings()
                settings = replace(
                    base_settings,
                    alerts_enabled=alerts_enabled,
                    alert_default_destination_email="ops@example.com",
                    alert_error_spike_min_requests=error_spike_min_requests,
                    alert_error_spike_ratio_threshold=error_spike_ratio_threshold,
                    alert_outage_min_requests=outage_min_requests,
                    alert_cooldown_minutes=cooldown_minutes,
                )
                triggered = await evaluate_alerts_once(
                    session,
                    settings,
                    sender=sender,
                    now=now,
                )
                dispatch_rows = await session.execute(text("SELECT COUNT(*) FROM alert_dispatches"))
                stored_count = int(dispatch_rows.scalar_one())
                return triggered, stored_count
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_alert_job_triggers_error_spike_and_suppresses_inside_cooldown(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=10,
        error_count=7,
        base_time=base_time,
    )

    first_triggered, first_stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=1),
        error_spike_min_requests=5,
        error_spike_ratio_threshold=0.5,
        outage_min_requests=50,
        cooldown_minutes=30,
    )
    second_triggered, second_stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=2),
        error_spike_min_requests=5,
        error_spike_ratio_threshold=0.5,
        outage_min_requests=50,
        cooldown_minutes=30,
    )

    assert first_triggered == 1
    assert first_stored == 1
    assert second_triggered == 0
    assert second_stored == 1


def test_alert_job_triggers_outage_when_no_success_requests(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=6,
        error_count=6,
        base_time=base_time,
    )

    triggered, stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=1),
        error_spike_min_requests=100,
        error_spike_ratio_threshold=0.95,
        outage_min_requests=5,
        cooldown_minutes=10,
    )

    assert triggered == 1
    assert stored == 1


def test_evaluate_alerts_returns_zero_when_alerts_disabled(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=30,
        error_count=25,
        base_time=base_time,
    )

    triggered, stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=1),
        error_spike_min_requests=5,
        error_spike_ratio_threshold=0.5,
        outage_min_requests=50,
        cooldown_minutes=30,
        alerts_enabled=False,
    )

    assert triggered == 0
    assert stored == 0


def test_evaluate_alerts_returns_zero_when_no_projects(backend_test_database_url: str) -> None:
    truncate_full_schema(backend_test_database_url)

    triggered, stored = _run_alert_job(
        backend_test_database_url,
        now=datetime.now(tz=UTC),
        error_spike_min_requests=1,
        error_spike_ratio_threshold=0.01,
        outage_min_requests=1,
        cooldown_minutes=1,
    )

    assert triggered == 0
    assert stored == 0


def test_evaluate_alerts_returns_zero_below_min_request_threshold(
    backend_test_database_url: str,
) -> None:
    """Default-style spike rule needs enough volume; sparse traffic should not dispatch."""
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=15,
        error_count=15,
        base_time=base_time,
    )

    triggered, stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=1),
        error_spike_min_requests=20,
        error_spike_ratio_threshold=0.4,
        outage_min_requests=50,
        cooldown_minutes=30,
    )

    assert triggered == 0
    assert stored == 0


def test_alert_sender_defaults_to_stub_when_webhook_mode_missing_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from lumonox_backend.alerts import StubAlertSender, build_alert_sender

    # Avoid invalid combinations from developer env (e.g. log_shards + sqlite).
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setenv("LUMONOX_EVENT_PLANE_MODE", "duckdb_single_writer")

    settings = replace(get_settings(), alert_sender_mode="webhook", alert_webhook_url=None)
    sender = build_alert_sender(settings)
    assert isinstance(sender, StubAlertSender)


class FailingSender:
    delivery_kind = "email"

    async def send(self, signal: AlertSignal) -> AlertDeliveryResult:
        return AlertDeliveryResult(
            status="failed",
            delivered_via=self.delivery_kind,
            reason_code="provider_rejected",
            attempt_count=3,
            detail={"delivery_error": "provider rejected"},
        )


def test_alert_dispatch_records_status_fields_on_failure(backend_test_database_url: str) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=10,
        error_count=7,
        base_time=base_time,
    )

    async def run() -> tuple[str, str | None, int]:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                settings = replace(
                    get_settings(),
                    alert_default_destination_email="ops@example.com",
                    alert_error_spike_min_requests=5,
                    alert_error_spike_ratio_threshold=0.5,
                    alert_outage_min_requests=100,
                    alert_cooldown_minutes=30,
                )
                triggered = await evaluate_alerts_once(
                    session,
                    settings,
                    sender=FailingSender(),
                    now=base_time + timedelta(minutes=1),
                )
                assert triggered == 0
                row = await session.execute(
                    text(
                        "SELECT status, reason_code, attempt_count FROM alert_dispatches "
                        "ORDER BY id DESC LIMIT 1"
                    )
                )
                status, reason_code, attempt_count = row.one()
                return (
                    str(status),
                    (str(reason_code) if reason_code is not None else None),
                    int(attempt_count),
                )
        finally:
            await engine.dispose()

    status, reason_code, attempt_count = asyncio.run(run())
    assert status == "failed"
    assert reason_code == "provider_rejected"
    assert attempt_count == 3


def test_email_sender_returns_missing_destination_when_email_not_set() -> None:
    sender = EmailAlertSender(
        provider="resend",
        api_key="test-key",
        from_email="alerts@example.com",
    )
    signal = AlertSignal(
        project_id=uuid4(),
        alert_type="error_spike",
        destination_email=None,
        triggered_at=datetime.now(tz=UTC),
        window_start=datetime.now(tz=UTC) - timedelta(minutes=1),
        window_end=datetime.now(tz=UTC),
        detail={"request_count": 10},
    )
    result = asyncio.run(sender.send(signal))
    assert result.status == "skipped"
    assert result.reason_code == "missing_destination"


def test_email_sender_file_provider_writes_outbox(tmp_path) -> None:
    sender = EmailAlertSender(
        provider="file",
        from_email="alerts@example.com",
        file_outbox_dir=str(tmp_path),
    )
    signal = AlertSignal(
        project_id=uuid4(),
        alert_type="error_spike",
        destination_email="ops@example.com",
        triggered_at=datetime.now(tz=UTC),
        window_start=datetime.now(tz=UTC) - timedelta(minutes=1),
        window_end=datetime.now(tz=UTC),
        detail={"request_count": 10},
    )
    result = asyncio.run(sender.send(signal))
    assert result.status == "sent"
    assert result.delivered_via == "email"
    assert result.detail is not None
    outbox_path = result.detail.get("outbox_path")
    assert isinstance(outbox_path, str)
    assert outbox_path.endswith(".eml")


def test_slack_webhook_sender_posts_incoming_webhook_text_payload() -> None:
    from lumonox_backend.services.alert_delivery import AlertSignal, SlackWebhookAlertSender

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post = AsyncMock(return_value=mock_response)
    async_client = MagicMock()
    async_client.post = mock_post
    async_cm = MagicMock()
    async_cm.__aenter__ = AsyncMock(return_value=async_client)
    async_cm.__aexit__ = AsyncMock(return_value=None)
    mock_client_factory = MagicMock(return_value=async_cm)

    client_patch = "lumonox_backend.services.alert_delivery.httpx.AsyncClient"

    async def run() -> object:
        with patch(client_patch, mock_client_factory):
            sender = SlackWebhookAlertSender(webhook_url="https://1.1.1.1/webhook-test")
            signal = AlertSignal(
                project_id=uuid4(),
                alert_type="error_spike",
                destination_email="ops@example.com",
                triggered_at=datetime.now(tz=UTC),
                window_start=datetime.now(tz=UTC) - timedelta(minutes=5),
                window_end=datetime.now(tz=UTC),
                detail={"request_count": 12, "error_ratio": 0.6},
            )
            return await sender.send(signal)

    result = asyncio.run(run())
    assert result.status == "sent"
    assert result.delivered_via == "slack"
    mock_client_factory.assert_called_once()
    assert mock_post.await_count == 1
    posted = mock_post.await_args
    assert posted is not None
    body = posted.kwargs.get("json")
    assert isinstance(body, dict)
    assert "text" in body
    assert "error_spike" in body["text"]


def _configure_alert_notifications(
    database_url: str,
    project_id: str,
    *,
    muted: bool = False,
    snoozed_until: datetime | None = None,
) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                settings = get_settings()
                row = await get_or_create_project_alert_settings(
                    session, UUID(project_id), settings
                )
                row.notifications_muted = muted
                row.notifications_snoozed_until = snoozed_until
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_evaluate_alerts_skips_when_notifications_muted(backend_test_database_url: str) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    project_id = _seed_request_events(
        backend_test_database_url,
        request_count=10,
        error_count=7,
        base_time=base_time,
    )
    _configure_alert_notifications(backend_test_database_url, project_id, muted=True)

    triggered, stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=1),
        error_spike_min_requests=5,
        error_spike_ratio_threshold=0.5,
        outage_min_requests=50,
        cooldown_minutes=30,
    )

    assert triggered == 0
    assert stored == 0


def test_evaluate_alerts_skips_when_notifications_snoozed(backend_test_database_url: str) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    project_id = _seed_request_events(
        backend_test_database_url,
        request_count=10,
        error_count=7,
        base_time=base_time,
    )
    eval_time = base_time + timedelta(minutes=1)
    _configure_alert_notifications(
        backend_test_database_url,
        project_id,
        snoozed_until=eval_time + timedelta(hours=2),
    )

    triggered, stored = _run_alert_job(
        backend_test_database_url,
        now=eval_time,
        error_spike_min_requests=5,
        error_spike_ratio_threshold=0.5,
        outage_min_requests=50,
        cooldown_minutes=30,
    )

    assert triggered == 0
    assert stored == 0
