from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lumonox_backend.dashboard.studio_nav_pages import list_studio_nav_pages
from lumonox_backend.dashboard.studio_showcase import (
    LX_STUDIO_PREFIX,
    build_studio_showcase_definitions,
)
from lumonox_backend.dashboard.widget_layout import build_widget_layout


def test_list_studio_nav_pages_includes_showcase_only_in_demo_mode() -> None:
    # Production default: the synthetic `lx_showcase` page is hidden from the sidebar.
    prod_pages = list_studio_nav_pages()
    assert "lx_showcase" not in {p.page_id for p in prod_pages}

    # Demo mode (LUMONOX_STUDIO_SHOWCASE_DEMO): the showcase page is registered.
    demo_pages = list_studio_nav_pages(include_demo=True)
    ids = {p.page_id for p in demo_pages}
    assert "lx_showcase" in ids
    showcase = next(p for p in demo_pages if p.page_id == "lx_showcase")
    assert showcase.pathname == "/w/lx_showcase"
    assert showcase.sidebar_label


def test_merge_studio_showcase_widgets_respects_demo_flag() -> None:
    from lumonox_backend.dashboard.studio_showcase import merge_studio_showcase_widgets

    now = datetime.now(tz=UTC)
    start = now - timedelta(hours=2)

    prod_defs, prod_pts = merge_studio_showcase_widgets([], [], start, now, demo_enabled=False)
    assert prod_defs == []
    assert prod_pts == []

    demo_defs, demo_pts = merge_studio_showcase_widgets([], [], start, now, demo_enabled=True)
    assert demo_defs
    assert demo_pts
    assert all(d.widget_id.startswith(LX_STUDIO_PREFIX) for d in demo_defs)


def test_showcase_definitions_cover_all_widget_types() -> None:
    defs = build_studio_showcase_definitions()
    types = {d.type for d in defs}
    assert types == {"card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"}
    assert all(d.widget_id.startswith(LX_STUDIO_PREFIX) for d in defs)
    layout = build_widget_layout(defs)
    page_ids = {p.page_id for p in layout.pages}
    assert page_ids == {"lx_showcase"}
    placements = layout.pages[0].widgets
    spans = {(p.column_span, p.row_span) for p in placements}
    assert (2, 1) in spans
    assert (3, 1) in spans
    assert (2, 2) in spans


def test_layout_sections_are_distinct() -> None:
    defs = build_studio_showcase_definitions()
    layout = build_widget_layout(defs)
    sections = {p.section for p in layout.pages[0].widgets}
    assert len(sections) >= 4


def test_showcase_points_cover_window() -> None:
    from lumonox_backend.dashboard.studio_showcase import build_studio_showcase_points

    now = datetime.now(tz=UTC)
    start = now - timedelta(hours=2)
    pts = build_studio_showcase_points(start, now)
    assert pts
    ids = {p.widget_id for p in pts}
    assert f"{LX_STUDIO_PREFIX}full_line" in ids


def test_showcase_stacked_area_has_ten_environment_series() -> None:
    from lumonox_backend.dashboard.studio_showcase import build_studio_showcase_points

    now = datetime.now(tz=UTC)
    start = now - timedelta(hours=2)
    pts = build_studio_showcase_points(start, now)
    stacked = [p for p in pts if p.widget_id == f"{LX_STUDIO_PREFIX}stacked"]
    labels = {p.label for p in stacked if p.label}
    assert len(labels) == 10
