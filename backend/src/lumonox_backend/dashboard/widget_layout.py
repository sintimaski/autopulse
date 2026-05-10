from __future__ import annotations

from collections import defaultdict

from lumonox_backend.schemas import (
    DashboardWidgetDefinition,
    DashboardWidgetLayout,
    DashboardWidgetPageLayout,
    DashboardWidgetPlacement,
)

_DEFAULT_PAGE_ID = "overview"
_DEFAULT_PAGE_TITLE = "Overview widgets"


def _coerce_int(value: object, default: int, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        parsed = int(value)
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return default
    else:
        return default
    return max(minimum, min(maximum, parsed))


def _safe_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def build_widget_layout(definitions: list[DashboardWidgetDefinition]) -> DashboardWidgetLayout:
    pages: dict[str, dict[str, object]] = {}
    page_widgets: defaultdict[str, list[DashboardWidgetPlacement]] = defaultdict(list)
    unplaced: list[str] = []

    for definition in definitions:
        page_id = _safe_string(definition.config.get("page_id")) or _DEFAULT_PAGE_ID
        page_title = _safe_string(definition.config.get("page_title"))
        page_description = _safe_string(definition.config.get("page_description"))
        page_order = _coerce_int(
            definition.config.get("page_order"),
            default=0 if page_id == _DEFAULT_PAGE_ID else 100,
            minimum=0,
            maximum=10_000,
        )
        section = _safe_string(definition.config.get("section")) or "default"
        placement_order = _coerce_int(
            definition.config.get("layout_order"),
            default=definition.order,
            minimum=0,
            maximum=1_000_000,
        )
        column_span = _coerce_int(
            definition.config.get("column_span"),
            default=1,
            minimum=1,
            maximum=3,
        )
        row_span = _coerce_int(
            definition.config.get("row_span"),
            default=1,
            minimum=1,
            maximum=4,
        )
        existing_meta = pages.get(page_id)
        if existing_meta is None:
            merged_order = page_order
        else:
            prev = _coerce_int(
                existing_meta.get("order"),
                default=page_order,
                minimum=0,
                maximum=10_000,
            )
            merged_order = min(prev, page_order)
        pages[page_id] = {
            "title": page_title
            or (existing_meta.get("title") if existing_meta else None)
            or page_id.replace("_", " ").title(),
            "description": page_description
            or (existing_meta.get("description") if existing_meta else None),
            "order": merged_order,
        }
        page_widgets[page_id].append(
            DashboardWidgetPlacement(
                widget_id=definition.widget_id,
                order=placement_order,
                section=section,
                column_span=column_span,
                row_span=row_span,
            )
        )

    page_layouts: list[DashboardWidgetPageLayout] = []
    for page_id, page_meta in pages.items():
        placements = sorted(
            page_widgets.get(page_id, []),
            key=lambda item: (item.section, item.order, item.widget_id),
        )
        if not placements:
            unplaced.extend(
                [item.widget_id for item in definitions if item.widget_id not in unplaced]
            )
            continue
        page_layouts.append(
            DashboardWidgetPageLayout(
                page_id=page_id,
                title=str(page_meta["title"]) or _DEFAULT_PAGE_TITLE,
                description=str(page_meta["description"])
                if isinstance(page_meta["description"], str)
                else None,
                order=_coerce_int(
                    page_meta.get("order"),
                    default=0,
                    minimum=0,
                    maximum=10_000,
                ),
                widgets=placements,
            )
        )

    page_layouts.sort(key=lambda item: (item.order, item.page_id))
    if not page_layouts:
        return DashboardWidgetLayout(
            default_page_id=_DEFAULT_PAGE_ID, pages=[], unplaced_widget_ids=unplaced
        )
    default_page_id = (
        _DEFAULT_PAGE_ID
        if any(page.page_id == _DEFAULT_PAGE_ID for page in page_layouts)
        else page_layouts[0].page_id
    )
    return DashboardWidgetLayout(
        default_page_id=default_page_id,
        pages=page_layouts,
        unplaced_widget_ids=unplaced,
    )
