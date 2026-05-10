from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from lumonox_backend.dashboard.widget_points_selection import (
    merge_narrow_window_with_infra_lookback,
)


def test_merge_narrow_window_keeps_infra_outside_overview_window() -> None:
    t_old = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    t_new = datetime(2026, 1, 1, 13, 30, tzinfo=UTC)
    resolved_from = t_new - timedelta(minutes=5)
    resolved_to = t_new + timedelta(minutes=5)

    points_raw = [
        SimpleNamespace(
            widget_id="infra_host_cpu_percent",
            timestamp=t_old,
            label=None,
            value=1.0,
        ),
        SimpleNamespace(
            widget_id="queue_depth",
            timestamp=t_new,
            label=None,
            value=2.0,
        ),
    ]
    out = merge_narrow_window_with_infra_lookback(
        points_raw,
        resolved_from=resolved_from,
        resolved_to=resolved_to,
    )
    assert len(out) == 2
    ids = {p.widget_id for p in out}
    assert ids == {"infra_host_cpu_percent", "queue_depth"}


def test_merge_narrow_window_returns_full_lookback_when_window_empty() -> None:
    t_a = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    t_b = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    window_start = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    window_end = datetime(2026, 1, 2, 1, 0, tzinfo=UTC)
    points_raw = [
        SimpleNamespace(widget_id="infra_host_cpu_percent", timestamp=t_a, label=None, value=1.0),
        SimpleNamespace(widget_id="infra_host_cpu_percent", timestamp=t_b, label=None, value=2.0),
    ]
    out = merge_narrow_window_with_infra_lookback(
        points_raw,
        resolved_from=window_start,
        resolved_to=window_end,
    )
    assert len(out) == 2
