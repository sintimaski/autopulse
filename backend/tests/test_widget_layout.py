from __future__ import annotations

from lumonox_backend.dashboard.widget_layout import build_widget_layout
from lumonox_backend.schemas import DashboardWidgetDefinition


def test_build_widget_layout_groups_by_page_and_preserves_order() -> None:
    definitions = [
        DashboardWidgetDefinition(
            widget_id="widget_one",
            type="card",
            title="One",
            description=None,
            order=20,
            config={
                "page_id": "overview",
                "page_title": "Overview widgets",
                "section": "kpis",
                "layout_order": 10,
            },
        ),
        DashboardWidgetDefinition(
            widget_id="widget_two",
            type="line",
            title="Two",
            description=None,
            order=30,
            config={
                "page_id": "ops",
                "page_title": "Operations",
                "page_order": 5,
                "section": "charts",
            },
        ),
    ]

    layout = build_widget_layout(definitions)
    assert layout.default_page_id == "overview"
    assert [page.page_id for page in layout.pages] == ["overview", "ops"]
    assert layout.pages[0].widgets[0].widget_id == "widget_one"
    assert layout.pages[1].widgets[0].widget_id == "widget_two"
