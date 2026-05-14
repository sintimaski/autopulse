"use client";

import { useMemo, useState } from "react";

import {
  BreakdownBarChart,
  ChartPanel,
  DonutChart,
  HistogramChart,
  ScatterPlotChart,
  StackedAreaChart,
  TimeSeriesLineChart,
  type ScatterPlotPoint,
  type StackedAreaSeries,
} from "../charts/lazyCharts";
import { MetricCard } from "../MetricCard";
import type {
  DashboardWidgetDefinition,
  DashboardWidgetPageLayout,
  DashboardWidgetPlacement,
  DashboardWidgetPoint,
  DashboardWidgetsResponse,
} from "../dashboardTypes";

type Props = {
  dashboardWidgets: DashboardWidgetsResponse | null;
  chartsScopePending?: boolean;
  /** When set, only this `page_id` is shown (no in-card page tabs). */
  lockedPageId?: string;
};

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

function collapseLatestByLabel(points: DashboardWidgetPoint[]): Array<{ key: string; value: number }> {
  const latestByLabel = new Map<string, DashboardWidgetPoint>();
  for (const point of points) {
    const label = point.label ?? new Date(point.timestamp).toLocaleTimeString();
    const existing = latestByLabel.get(label);
    if (!existing || existing.timestamp < point.timestamp) {
      latestByLabel.set(label, point);
    }
  }
  return [...latestByLabel.entries()]
    .map(([key, point]) => ({ key, value: point.value }))
    .sort((a, b) => b.value - a.value);
}

function inferPageLayout(definitions: DashboardWidgetDefinition[]): DashboardWidgetPageLayout[] {
  return [
    {
      page_id: "overview",
      title: "Overview widgets",
      description: "Server-built widget snapshots for this scope window.",
      order: 0,
      widgets: definitions
        .map((item) => ({
          widget_id: item.widget_id,
          order: item.order,
          section: item.type === "card" ? "kpis" : "charts",
          column_span: 1,
          row_span: 1,
        }))
        .sort((a, b) => a.order - b.order),
    },
  ];
}

function layoutColSpanClass(span: number | undefined): string {
  const s = Math.min(Math.max(span ?? 1, 1), 3);
  if (s <= 1) return "sm:col-span-1";
  if (s === 2) return "sm:col-span-2";
  return "sm:col-span-3";
}

function layoutRowSpanClass(span: number | undefined): string {
  const s = Math.min(Math.max(span ?? 1, 1), 4);
  if (s <= 1) return "";
  if (s === 2) return "sm:row-span-2";
  if (s === 3) return "sm:row-span-3";
  return "sm:row-span-4";
}

function sectionHeading(section: string): string {
  if (section === "default") return "General";
  return section
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function DashboardHomeOverviewWidgets({ dashboardWidgets, chartsScopePending, lockedPageId }: Props) {
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

  const pages = useMemo(() => {
    const src =
      dashboardWidgets?.layout?.pages && dashboardWidgets.layout.pages.length > 0
        ? [...dashboardWidgets.layout.pages].sort((a, b) => a.order - b.order)
        : inferPageLayout(dashboardWidgets?.definitions ?? []);
    if (lockedPageId) {
      return src.filter((page) => page.page_id === lockedPageId);
    }
    return src;
  }, [dashboardWidgets, lockedPageId]);

  const defaultUnlockedPageId = useMemo(() => {
    const layout = dashboardWidgets?.layout;
    if (layout?.default_page_id && pages.some((page) => page.page_id === layout.default_page_id)) {
      return layout.default_page_id;
    }
    return pages[0]?.page_id ?? "";
  }, [dashboardWidgets, pages]);

  const [pickedPageId, setPickedPageId] = useState<string | null>(null);

  const activePageId = useMemo(() => {
    if (lockedPageId && pages.some((page) => page.page_id === lockedPageId)) {
      return lockedPageId;
    }
    if (pickedPageId && pages.some((page) => page.page_id === pickedPageId)) {
      return pickedPageId;
    }
    return defaultUnlockedPageId;
  }, [defaultUnlockedPageId, lockedPageId, pages, pickedPageId]);

  const activePage = pages.find((page) => page.page_id === activePageId) ?? pages[0];

  const orderedWidgets = useMemo(() => {
    if (!activePage) {
      return [] as DashboardWidgetPlacement[];
    }
    return activePage.widgets
      .filter((placement) => defsById.has(placement.widget_id))
      .sort((a, b) => a.order - b.order);
  }, [activePage, defsById]);

  const sectionOrder = useMemo(() => {
    const keys: string[] = [];
    for (const w of orderedWidgets) {
      if (!keys.includes(w.section)) {
        keys.push(w.section);
      }
    }
    return keys;
  }, [orderedWidgets]);

  const renderWidget = (widgetId: string) => {
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
      const items = collapseLatestByLabel(points);
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

    if (widget.type === "line") {
      return (
        <ChartPanel key={widgetId} title={widget.title} description={widget.description ?? undefined}>
          <TimeSeriesLineChart
            title={widget.title}
            labels={points.map((point) => new Date(point.timestamp).toLocaleTimeString())}
            values={points.map((point) => point.value)}
            color={typeof widget.config?.color === "string" ? widget.config.color : "#38bdf8"}
            formatValue={(value) => value.toFixed(2)}
            live
            chartsScopePending={chartsScopePending}
          />
        </ChartPanel>
      );
    }

    if (widget.type === "histogram") {
      const buckets = collapseLatestByLabel(points).map((item) => ({
        label: item.key,
        count: Math.max(0, Math.round(item.value)),
      }));
      return (
        <ChartPanel key={widgetId} title={widget.title} description={widget.description ?? undefined}>
          <HistogramChart buckets={buckets} />
        </ChartPanel>
      );
    }

    if (widget.type === "scatter") {
      const scatterPoints: ScatterPlotPoint[] = points.map((point, index) => {
        const [xValueRaw, freeLabel] = String(point.label ?? "").split("|", 2);
        const parsedX = Number(xValueRaw);
        const x = Number.isFinite(parsedX) ? parsedX : index + 1;
        const y = Number(point.value || 0);
        return {
          id: `${widget.widget_id}-${index}`,
          x,
          y,
          label: freeLabel?.trim() ? `${freeLabel} · x=${x.toFixed(2)} · y=${y.toFixed(2)}` : `x=${x.toFixed(2)} · y=${y.toFixed(2)}`,
          tone: y >= 10 ? "danger" : y >= 3 ? "warning" : "neutral",
        };
      });
      return (
        <ChartPanel key={widgetId} title={widget.title} description={widget.description ?? undefined}>
          <ScatterPlotChart
            points={scatterPoints}
            xLabel={typeof widget.config?.x_label === "string" ? widget.config.x_label : "X axis"}
            yLabel={typeof widget.config?.y_label === "string" ? widget.config.y_label : "Y axis"}
          />
        </ChartPanel>
      );
    }

    if (widget.type === "stacked_area") {
      const timestampKeys = [...new Set(points.map((point) => point.timestamp))].sort((a, b) => a.localeCompare(b));
      const labels = timestampKeys.map((ts) => new Date(ts).toLocaleTimeString());
      const bySeries = new Map<string, Map<string, number>>();
      for (const point of points) {
        const seriesName = point.label ?? "series";
        const entry = bySeries.get(seriesName) ?? new Map<string, number>();
        entry.set(point.timestamp, point.value);
        bySeries.set(seriesName, entry);
      }
      const palette = [
        "#34d399",
        "#38bdf8",
        "#f59e0b",
        "#f43f5e",
        "#fb923c",
        "#a78bfa",
        "#2dd4bf",
        "#fb7185",
        "#eab308",
        "#64748b",
      ];
      const series: StackedAreaSeries[] = [...bySeries.entries()].map(([seriesName, valuesByTs], index) => ({
        id: `${widget.widget_id}-${seriesName}`,
        label: seriesName,
        color: palette[index % palette.length],
        values: timestampKeys.map((ts) => Number(valuesByTs.get(ts) ?? 0)),
      }));
      return (
        <ChartPanel key={widgetId} title={widget.title} description={widget.description ?? undefined}>
          <StackedAreaChart labels={labels} series={series} live chartsScopePending={chartsScopePending} />
        </ChartPanel>
      );
    }

    const slices = collapseLatestByLabel(points).map((item, index) => ({
      id: `${widgetId}-${index}`,
      label: item.key,
      value: item.value,
      color: ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#fb923c"][index % 5],
    }));
    return (
      <ChartPanel key={widgetId} title={widget.title} description={widget.description ?? undefined}>
        <DonutChart title={widget.title} items={slices} />
      </ChartPanel>
    );
  };

  if (lockedPageId && pages.length === 0) {
    return (
      <div className="rounded-xl border border-amber-500/35 bg-amber-50/90 p-4 text-sm text-amber-950 dark:border-amber-500/30 dark:bg-amber-950/35 dark:text-amber-100">
        No widget page <code className="rounded bg-white/60 px-1 dark:bg-neutral-900/60">{lockedPageId}</code> in the
        current payload. Register it in backend studio nav and widget definitions.
      </div>
    );
  }

  if (!activePage) {
    return null;
  }

  const showPageTabs = Boolean(!lockedPageId && pages.length > 1);

  return (
    <section className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">{activePage.title}</h3>
        {showPageTabs ? (
          <div className="flex flex-wrap items-center gap-1">
            {pages.map((page) => (
              <button
                key={page.page_id}
                type="button"
                onClick={() => setPickedPageId(page.page_id)}
                className={`rounded-md border px-2 py-1 text-xs ${
                  page.page_id === activePage.page_id
                    ? "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-200"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
                }`}
              >
                {page.title}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
        {activePage.description ?? "Backend-managed widget page. Configure layout via widget definition config on the backend."}
      </p>
      <div className="mt-4 space-y-8">
        {sectionOrder.map((sectionKey) => (
          <div key={sectionKey} className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
              {sectionHeading(sectionKey)}
            </h4>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:grid-flow-dense auto-rows-min">
              {orderedWidgets
                .filter((placement) => placement.section === sectionKey)
                .map((placement) => (
                  <div
                    key={placement.widget_id}
                    className={`min-w-0 ${layoutColSpanClass(placement.column_span)} ${layoutRowSpanClass(placement.row_span)}`}
                  >
                    {renderWidget(placement.widget_id)}
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
