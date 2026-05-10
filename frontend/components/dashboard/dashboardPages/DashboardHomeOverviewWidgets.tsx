"use client";

import { useMemo } from "react";

import { BreakdownBarChart, ChartPanel, DonutChart } from "../charts/lazyCharts";
import { MetricCard } from "../MetricCard";
import type {
  DashboardWidgetDefinition,
  DashboardWidgetPoint,
  DashboardWidgetsResponse,
} from "../dashboardTypes";

/** Must match ``lx_home_*`` ids from ``lumonox_backend.dashboard.overview_derived_widgets`` */
export const LX_HOME_OVERVIEW_WIDGET_ORDER = [
  "lx_home_status_donut",
  "lx_home_peak_minutes_bar",
  "lx_home_window_requests",
  "lx_home_window_avg_latency",
] as const;

type Props = {
  dashboardWidgets: DashboardWidgetsResponse | null;
  chartsScopePending?: boolean;
};

function latestByLabel(points: DashboardWidgetPoint[]): Array<{ key: string; value: number }> {
  const latest = new Map<string, DashboardWidgetPoint>();
  for (const point of points) {
    const label = point.label ?? new Date(point.timestamp).toLocaleTimeString();
    const existing = latest.get(label);
    if (!existing || existing.timestamp < point.timestamp) {
      latest.set(label, point);
    }
  }
  return [...latest.entries()]
    .map(([key, point]) => ({ key, value: point.value }))
    .sort((a, b) => b.value - a.value);
}

function formatCardValue(widgetId: string, raw: number | undefined): string {
  if (raw === undefined || Number.isNaN(raw)) {
    return "—";
  }
  if (widgetId === "lx_home_window_requests") {
    return Math.round(raw).toLocaleString();
  }
  if (widgetId === "lx_home_window_avg_latency") {
    return raw.toFixed(1);
  }
  return raw.toFixed(2);
}

function cardSuffix(widgetId: string, unit: string | undefined): string {
  if (widgetId === "lx_home_window_avg_latency") {
    return " ms";
  }
  if (unit) {
    return ` ${unit}`;
  }
  return "";
}

export function DashboardHomeOverviewWidgets({ dashboardWidgets, chartsScopePending }: Props) {
  const defsById = useMemo(() => {
    const map = new Map<string, DashboardWidgetDefinition>();
    for (const d of dashboardWidgets?.definitions ?? []) {
      map.set(d.widget_id, d);
    }
    return map;
  }, [dashboardWidgets?.definitions]);

  const pointsById = useMemo(() => {
    const map = new Map<string, DashboardWidgetPoint[]>();
    for (const p of dashboardWidgets?.points ?? []) {
      const list = map.get(p.widget_id) ?? [];
      list.push(p);
      map.set(p.widget_id, list);
    }
    return map;
  }, [dashboardWidgets?.points]);

  const present = LX_HOME_OVERVIEW_WIDGET_ORDER.filter((id) => defsById.has(id));
  if (present.length === 0) {
    return null;
  }

  return (
    <section className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06]">
      <h3 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Window snapshot</h3>
      <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
        Server-built widgets from the same overview window as your traffic cards (status mix, busiest buckets, volume,
        latency).
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {LX_HOME_OVERVIEW_WIDGET_ORDER.map((widgetId) => {
          const widget = defsById.get(widgetId);
          if (!widget) {
            return null;
          }
          const points = (pointsById.get(widgetId) ?? []).sort((a, b) => a.timestamp.localeCompare(b.timestamp));

          if (widget.type === "card") {
            const latest = points[points.length - 1];
            const unit = typeof widget.config?.unit === "string" ? widget.config.unit : "";
            const v = latest?.value;
            const tone =
              widgetId === "lx_home_window_avg_latency" && typeof v === "number" && v >= 500
                ? ("danger" as const)
                : widgetId === "lx_home_window_avg_latency" && typeof v === "number" && v >= 200
                  ? ("warning" as const)
                  : ("neutral" as const);
            return (
              <MetricCard
                key={widgetId}
                label={widget.title}
                value={`${formatCardValue(widgetId, v)}${cardSuffix(widgetId, unit)}`}
                helper={widget.description ?? ""}
                tone={tone}
              />
            );
          }

          if (widget.type === "bar") {
            const items = latestByLabel(points);
            return (
              <ChartPanel key={widgetId} title={widget.title} description={widget.description ?? undefined}>
                <BreakdownBarChart
                  items={items}
                  valueLabel="req"
                  emptyMessage="No bucket traffic in this window."
                  live
                  chartsScopePending={chartsScopePending}
                />
              </ChartPanel>
            );
          }

          const slices = latestByLabel(points).map((item, index) => ({
            id: `${widgetId}-${index}`,
            label: item.key,
            value: item.value,
            color: ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#818cf8"][index % 5],
          }));
          return (
            <ChartPanel key={widgetId} title={widget.title} description={widget.description ?? undefined}>
              <DonutChart title={widget.title} items={slices} />
            </ChartPanel>
          );
        })}
      </div>
    </section>
  );
}
