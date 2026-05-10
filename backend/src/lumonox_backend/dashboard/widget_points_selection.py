"""Widget point selection for dashboard responses."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from lumonox_backend.dashboard.time_window import as_utc_datetime


class _WidgetPointLike(Protocol):
    widget_id: str
    timestamp: datetime
    label: str | None
    value: float


def merge_narrow_window_with_infra_lookback(
    points_raw: Sequence[_WidgetPointLike],
    *,
    resolved_from: datetime,
    resolved_to: datetime,
) -> list[_WidgetPointLike]:
    """Return in-window points, or full lookback when the window is empty.

    When the overview window contains traffic-derived points but host samples only exist
    slightly outside that window (sparse infra vs tight ``resolved_from``), append those
    ``infra_*`` rows from ``points_raw`` so infrastructure charts still receive data.
    """
    narrow = [p for p in points_raw if resolved_from <= as_utc_datetime(p.timestamp) <= resolved_to]
    if not narrow:
        return list(points_raw)

    def _key(p: _WidgetPointLike) -> tuple[str, datetime, str | None]:
        return (p.widget_id, as_utc_datetime(p.timestamp), p.label)

    keys = {_key(p) for p in narrow}
    points: list[_WidgetPointLike] = list(narrow)
    for p in points_raw:
        if not p.widget_id.startswith("infra_"):
            continue
        k = _key(p)
        if k in keys:
            continue
        keys.add(k)
        points.append(p)

    points.sort(key=lambda p: (as_utc_datetime(p.timestamp), p.widget_id))
    return points
