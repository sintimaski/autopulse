from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

WidgetType = Literal["card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"]


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class BaseDashboardWidget:
    widget_id: str
    title: str
    description: str | None = None
    order: int = 100
    page_id: str = "custom"
    page_title: str | None = None
    page_description: str | None = None
    page_order: int = 100
    section: str = "default"
    column_span: int = 1
    row_span: int = 1

    @property
    def widget_type(self) -> WidgetType:
        raise NotImplementedError

    def serialize_definition(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "type": self.widget_type,
            "title": self.title,
            "description": self.description,
            "order": self.order,
            "config": self._layout_config(),
        }

    def collect_points(self) -> list[dict[str, Any]]:
        return []

    def _layout_config(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_title": self.page_title,
            "page_description": self.page_description,
            "page_order": self.page_order,
            "section": self.section,
            "column_span": self.column_span,
            "row_span": self.row_span,
        }


@dataclass(slots=True)
class CardWidget(BaseDashboardWidget):
    value: float = 0.0
    unit: str | None = None
    tone: Literal["neutral", "warning", "danger"] = "neutral"

    @property
    def widget_type(self) -> WidgetType:
        return "card"

    def collect_points(self) -> list[dict[str, Any]]:
        return [
            {
                "widget_id": self.widget_id,
                "timestamp": _utc_now_iso(),
                "value": float(self.value),
            }
        ]

    def serialize_definition(self) -> dict[str, Any]:
        payload = BaseDashboardWidget.serialize_definition(self)
        payload["config"] = {
            **self._layout_config(),
            "unit": self.unit,
            "tone": self.tone,
        }
        return payload


@dataclass(slots=True)
class LineChartWidget(BaseDashboardWidget):
    points: list[tuple[datetime | str, float]] | None = None
    color: str = "#38bdf8"
    unit: str | None = None

    @property
    def widget_type(self) -> WidgetType:
        return "line"

    def collect_points(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for timestamp, value in self.points or []:
            ts = (
                timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if isinstance(timestamp, datetime)
                else str(timestamp)
            )
            result.append({"widget_id": self.widget_id, "timestamp": ts, "value": float(value)})
        return result

    def serialize_definition(self) -> dict[str, Any]:
        payload = BaseDashboardWidget.serialize_definition(self)
        payload["config"] = {
            **self._layout_config(),
            "color": self.color,
            "unit": self.unit,
        }
        return payload


@dataclass(slots=True)
class BarChartWidget(BaseDashboardWidget):
    bars: list[tuple[str, float]] | None = None
    unit: str | None = None

    @property
    def widget_type(self) -> WidgetType:
        return "bar"

    def collect_points(self) -> list[dict[str, Any]]:
        return [
            {
                "widget_id": self.widget_id,
                "timestamp": _utc_now_iso(),
                "label": label,
                "value": float(value),
            }
            for label, value in (self.bars or [])
        ]

    def serialize_definition(self) -> dict[str, Any]:
        payload = BaseDashboardWidget.serialize_definition(self)
        payload["config"] = {
            **self._layout_config(),
            "unit": self.unit,
        }
        return payload


@dataclass(slots=True)
class DonutChartWidget(BaseDashboardWidget):
    slices: list[tuple[str, float]] | None = None

    @property
    def widget_type(self) -> WidgetType:
        return "donut"

    def collect_points(self) -> list[dict[str, Any]]:
        return [
            {
                "widget_id": self.widget_id,
                "timestamp": _utc_now_iso(),
                "label": label,
                "value": float(value),
            }
            for label, value in (self.slices or [])
        ]


@dataclass(slots=True)
class HistogramWidget(BaseDashboardWidget):
    buckets: list[tuple[str, float]] | None = None
    unit: str | None = None

    @property
    def widget_type(self) -> WidgetType:
        return "histogram"

    def collect_points(self) -> list[dict[str, Any]]:
        return [
            {
                "widget_id": self.widget_id,
                "timestamp": _utc_now_iso(),
                "label": label,
                "value": float(value),
            }
            for label, value in (self.buckets or [])
        ]

    def serialize_definition(self) -> dict[str, Any]:
        payload = BaseDashboardWidget.serialize_definition(self)
        payload["config"] = {
            **self._layout_config(),
            "unit": self.unit,
        }
        return payload


@dataclass(slots=True)
class ScatterPlotWidget(BaseDashboardWidget):
    # x is stored in label for compatibility with the existing point schema.
    points: list[tuple[float, float, str | None]] | None = None
    x_label: str = "X axis"
    y_label: str = "Y axis"

    @property
    def widget_type(self) -> WidgetType:
        return "scatter"

    def collect_points(self) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for x_value, y_value, label in self.points or []:
            point_label = str(float(x_value)) if label is None else f"{float(x_value)}|{label}"
            payload.append(
                {
                    "widget_id": self.widget_id,
                    "timestamp": _utc_now_iso(),
                    "label": point_label,
                    "value": float(y_value),
                }
            )
        return payload

    def serialize_definition(self) -> dict[str, Any]:
        payload = BaseDashboardWidget.serialize_definition(self)
        payload["config"] = {
            **self._layout_config(),
            "x_label": self.x_label,
            "y_label": self.y_label,
        }
        return payload


@dataclass(slots=True)
class StackedAreaWidget(BaseDashboardWidget):
    # points: (timestamp, series_label, value)
    points: list[tuple[datetime | str, str, float]] | None = None

    @property
    def widget_type(self) -> WidgetType:
        return "stacked_area"

    def collect_points(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for timestamp, series_label, value in self.points or []:
            ts = (
                timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if isinstance(timestamp, datetime)
                else str(timestamp)
            )
            rows.append(
                {
                    "widget_id": self.widget_id,
                    "timestamp": ts,
                    "label": series_label,
                    "value": float(value),
                }
            )
        return rows


def serialize_dashboard_widgets(
    widgets: list[BaseDashboardWidget] | tuple[BaseDashboardWidget, ...] | None,
) -> dict[str, list[dict[str, Any]]]:
    if not widgets:
        return {"definitions": [], "points": []}
    definitions = [widget.serialize_definition() for widget in widgets]
    points: list[dict[str, Any]] = []
    for widget in widgets:
        points.extend(widget.collect_points())
    return {"definitions": definitions, "points": points}
