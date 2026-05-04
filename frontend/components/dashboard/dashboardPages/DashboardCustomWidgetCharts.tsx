"use client";

import { useMemo } from "react";

import { MetricCard } from "../MetricCard";
import {
  BreakdownBarChart,
  ChartPanel,
  DonutChart,
  HistogramChart,
  ScatterPlotChart,
  StackedAreaChart,
  TimeSeriesLineChart,
  type ScatterPlotPoint,
} from "../charts";
import type { DashboardWidgetDefinition, DashboardWidgetPoint } from "../dashboardTypes";

const widgetSeriesPalette = ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#818cf8", "#a78bfa"];

function filterRenderableWidgetDefinitions(
  definitions: DashboardWidgetDefinition[] | undefined | null,
): DashboardWidgetDefinition[] {
  return (definitions ?? []).filter(
    (item): item is DashboardWidgetDefinition =>
      item.type === "card" ||
      item.type === "line" ||
      item.type === "bar" ||
      item.type === "donut" ||
      item.type === "histogram" ||
      item.type === "scatter" ||
      item.type === "stacked_area",
  );
}

export function DashboardCustomWidgetCharts({
  definitions,
  points,
  heading = "Custom widgets",
  description = "Rendered from widget definitions and time-series points.",
  emptyMessage = "No widget definitions to render.",
}: {
  definitions: DashboardWidgetDefinition[];
  points: DashboardWidgetPoint[];
  heading?: string;
  description?: string;
  emptyMessage?: string;
}) {
  const widgetDefinitions = useMemo(() => filterRenderableWidgetDefinitions(definitions), [definitions]);
  const widgetPointsById = useMemo(() => {
    const map = new Map<string, DashboardWidgetPoint[]>();
    for (const point of points) {
      const existing = map.get(point.widget_id) ?? [];
      existing.push(point);
      map.set(point.widget_id, existing);
    }
    return map;
  }, [points]);

  if (!widgetDefinitions.length) {
    return <p className="text-sm text-slate-600 dark:text-neutral-400">{emptyMessage}</p>;
  }

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">{heading}</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">{description}</p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {widgetDefinitions.map((widget) => {
          const widgetPoints = (widgetPointsById.get(widget.widget_id) ?? []).sort((a, b) =>
            a.timestamp.localeCompare(b.timestamp),
          );
          if (widget.type === "card") {
            const latest = widgetPoints[widgetPoints.length - 1];
            const tone =
              String(widget.config?.tone) === "danger"
                ? "danger"
                : String(widget.config?.tone) === "warning"
                  ? "warning"
                  : "neutral";
            const unit = typeof widget.config?.unit === "string" ? widget.config.unit : "";
            return (
              <MetricCard
                key={widget.widget_id}
                label={widget.title}
                value={`${latest?.value?.toFixed(2) ?? "0"}${unit ? ` ${unit}` : ""}`}
                helper={widget.description ?? "Custom KPI"}
                tone={tone}
              />
            );
          }
          if (widget.type === "line") {
            return (
              <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                <TimeSeriesLineChart
                  title={widget.title}
                  labels={widgetPoints.map((point) => new Date(point.timestamp).toLocaleTimeString())}
                  values={widgetPoints.map((point) => point.value)}
                  color={typeof widget.config?.color === "string" ? widget.config.color : "#38bdf8"}
                  formatValue={(value) => value.toFixed(2)}
                />
              </ChartPanel>
            );
          }
          if (widget.type === "bar") {
            const latestByLabel = new Map<string, DashboardWidgetPoint>();
            for (const point of widgetPoints) {
              const label = point.label ?? new Date(point.timestamp).toLocaleTimeString();
              const existing = latestByLabel.get(label);
              if (!existing || existing.timestamp < point.timestamp) {
                latestByLabel.set(label, point);
              }
            }
            const collapsedBars = [...latestByLabel.entries()]
              .map(([label, point]) => ({ key: label, value: point.value }))
              .sort((a, b) => b.value - a.value);
            return (
              <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                <BreakdownBarChart items={collapsedBars} />
              </ChartPanel>
            );
          }
          if (widget.type === "histogram") {
            const latestByLabel = new Map<string, DashboardWidgetPoint>();
            for (const point of widgetPoints) {
              const label = point.label ?? new Date(point.timestamp).toLocaleTimeString();
              const existing = latestByLabel.get(label);
              if (!existing || existing.timestamp < point.timestamp) {
                latestByLabel.set(label, point);
              }
            }
            const buckets = [...latestByLabel.entries()].map(([label, point]) => ({
              label,
              count: Math.max(0, Math.round(point.value)),
            }));
            return (
              <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                <HistogramChart buckets={buckets} />
              </ChartPanel>
            );
          }
          if (widget.type === "scatter") {
            const scatterPoints: ScatterPlotPoint[] = widgetPoints.map((point, index) => {
              const [xValueRaw, freeLabel] = String(point.label ?? "").split("|", 2);
              const parsedX = Number(xValueRaw);
              const x = Number.isFinite(parsedX) ? parsedX : index + 1;
              const y = Number(point.value || 0);
              const label = freeLabel?.trim()
                ? `${freeLabel} · x=${x.toFixed(2)} · y=${y.toFixed(2)}`
                : `x=${x.toFixed(2)} · y=${y.toFixed(2)}`;
              return {
                id: `${widget.widget_id}-${index}`,
                x,
                y,
                label,
                tone: y >= 10 ? "danger" : y >= 3 ? "warning" : "neutral",
              };
            });
            return (
              <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                <ScatterPlotChart
                  points={scatterPoints}
                  xLabel={typeof widget.config?.x_label === "string" ? widget.config.x_label : "X axis"}
                  yLabel={typeof widget.config?.y_label === "string" ? widget.config.y_label : "Y axis"}
                />
              </ChartPanel>
            );
          }
          if (widget.type === "stacked_area") {
            const timestampLabels = [...new Set(widgetPoints.map((point) => point.timestamp))]
              .sort((a, b) => a.localeCompare(b))
              .map((ts) => new Date(ts).toLocaleTimeString());
            const timestampKeys = [...new Set(widgetPoints.map((point) => point.timestamp))].sort((a, b) =>
              a.localeCompare(b),
            );
            const bySeries = new Map<string, Map<string, number>>();
            for (const point of widgetPoints) {
              const seriesName = point.label ?? "series";
              const entry = bySeries.get(seriesName) ?? new Map<string, number>();
              entry.set(point.timestamp, point.value);
              bySeries.set(seriesName, entry);
            }
            const stackedSeries = [...bySeries.entries()].map(([seriesName, valuesByTs], index) => ({
              id: `${widget.widget_id}-${seriesName}`,
              label: seriesName,
              color: widgetSeriesPalette[index % widgetSeriesPalette.length],
              values: timestampKeys.map((ts) => Number(valuesByTs.get(ts) ?? 0)),
            }));
            return (
              <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                <StackedAreaChart labels={timestampLabels} series={stackedSeries} />
              </ChartPanel>
            );
          }
          const latestByLabel = new Map<string, DashboardWidgetPoint>();
          for (const point of widgetPoints) {
            const label = point.label ?? "Value";
            const existing = latestByLabel.get(label);
            if (!existing || existing.timestamp < point.timestamp) {
              latestByLabel.set(label, point);
            }
          }
          const collapsedSlices = [...latestByLabel.entries()]
            .map(([label, point], index) => ({
              id: `${widget.widget_id}-${index}`,
              label,
              value: point.value,
              color: ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#818cf8"][index % 5],
            }))
            .sort((a, b) => b.value - a.value);
          return (
            <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
              <DonutChart title={widget.title} items={collapsedSlices} />
            </ChartPanel>
          );
        })}
      </div>
    </section>
  );
}
