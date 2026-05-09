from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.models import AlertDispatch


def record_alert_dispatch(
    session: AsyncSession,
    signal: Any,
    *,
    delivered_via: str,
    detail: dict[str, float | int | str] | None = None,
    status: str = "sent",
    reason_code: str | None = None,
    attempt_count: int = 1,
    delivered_at: Any | None = None,
    provider_message_id: str | None = None,
) -> None:
    payload = detail if detail is not None else signal.detail
    session.add(
        AlertDispatch(
            project_id=signal.project_id,
            alert_type=signal.alert_type,
            destination_email=signal.destination_email,
            delivered_via=delivered_via,
            status=status,
            reason_code=reason_code,
            attempt_count=max(1, int(attempt_count)),
            triggered_at=signal.triggered_at,
            window_start=signal.window_start,
            window_end=signal.window_end,
            delivered_at=delivered_at,
            provider_message_id=provider_message_id,
            detail=payload,
        )
    )
