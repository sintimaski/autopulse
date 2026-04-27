from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.models import AlertDispatch


def record_alert_dispatch(
    session: AsyncSession,
    signal: Any,
    *,
    delivered_via: str,
    detail: dict[str, float | int | str] | None = None,
) -> None:
    payload = detail if detail is not None else signal.detail
    session.add(
        AlertDispatch(
            project_id=signal.project_id,
            alert_type=signal.alert_type,
            destination_email=signal.destination_email,
            delivered_via=delivered_via,
            triggered_at=signal.triggered_at,
            window_start=signal.window_start,
            window_end=signal.window_end,
            detail=payload,
        )
    )
