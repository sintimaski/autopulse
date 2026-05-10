"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasLine } from "./chartCanvas";

export type StackedAreaSeries = {
  id: string;
  label: string;
  color: string;
  /** Y values rendered in the chart (stacked layers). */
  values: number[];
  /** Raw samples for tooltip/footer when `values` are derived (e.g. normalized composition). */
  tooltipRawValues?: number[];
  tooltipFormat?: (raw: number) => string;
};

type StackedAreaChartProps = {
  labels: string[];
  series: StackedAreaSeries[];
  height?: number;
  /** `stacked` (default): summed layers. `overlay`: shared Y axis, semi-transparent fills (e.g. % utilization). */
  variant?: "stacked" | "overlay";
  onPointClick?: (index: number, label: string, values: Record<string, number>) => void;
  /** Skip Chart.js tween on data updates (live dashboard refresh). */
  live?: boolean;
  /** Override default assistive summary (built from series labels and time span). */
  accessibilityLabel?: string;
};

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "").trim();
  if (h.length === 6) {
    const r = Number.parseInt(h.slice(0, 2), 16);
    const g = Number.parseInt(h.slice(2, 4), 16);
    const b = Number.parseInt(h.slice(4, 6), 16);
    if ([r, g, b].every((n) => Number.isFinite(n))) {
      return `rgba(${r},${g},${b},${alpha})`;
    }
  }
  return `rgba(100, 116, 139, ${alpha})`;
}

export function StackedAreaChart({
  labels,
  series,
  height = 124,
  variant = "stacked",
  onPointClick,
  live = false,
  accessibilityLabel,
}: StackedAreaChartProps) {
  const hasData = useMemo(() => Boolean(labels.length && series.length), [labels.length, series.length]);

  const pointCount = labels.length;

  const chartAccessibilityLabel = useMemo(() => {
    if (accessibilityLabel?.trim()) {
      return accessibilityLabel.trim();
    }
    if (!hasData) {
      return "Stacked area chart, no data in range";
    }
    const seriesNames = series.map((s) => s.label).join(", ");
    const from = labels[0] ?? "";
    const to = labels[labels.length - 1] ?? "";
    return `Stacked area chart: ${seriesNames}. ${pointCount} time buckets from ${from} to ${to}.`;
  }, [accessibilityLabel, hasData, labels, pointCount, series]);
  const isOverlay = variant === "overlay";

  const maxStack = useMemo(
    () =>
      hasData
        ? isOverlay
          ? Math.max(
              1,
              ...series.flatMap((entry) => entry.values.map((v) => Math.max(0, Number(v ?? 0)))),
            )
          : Math.max(
              1,
              ...Array.from({ length: pointCount }, (_, idx) =>
                series.reduce((sum, entry) => sum + Math.max(0, Number(entry.values[idx] ?? 0)), 0),
              ),
            )
        : 1,
    [hasData, isOverlay, pointCount, series],
  );

  const chartData = useMemo((): ChartData<"line"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"line">[] };
    }
    const fillAlpha = isOverlay ? 0.22 : 0.32;
    return {
      labels,
      datasets: series.map((entry) => ({
        label: entry.label,
        data: entry.values.map((v) => Math.max(0, Number(v ?? 0))),
        borderColor: entry.color,
        backgroundColor: hexToRgba(entry.color, fillAlpha),
        borderWidth: 1.5,
        tension: 0.25,
        fill: true,
        ...(isOverlay ? {} : { stack: "stack0" }),
        pointRadius: 0,
        pointHoverRadius: 3,
      })) as ChartDataset<"line">[],
    };
  }, [hasData, isOverlay, labels, series]);

  const options = useMemo<ChartOptions<"line">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: !hasData || labels.length > 120 || live ? 0 : 400 },
      interaction: { mode: "index", intersect: false },
      onClick: (_event, elements) => {
        if (!hasData || !onPointClick || !elements.length) {
          return;
        }
        const idx = elements[0].index;
        const pointValues = series.reduce<Record<string, number>>((acc, entry) => {
          acc[entry.id] = Number(entry.values[idx] ?? 0);
          return acc;
        }, {});
        onPointClick(idx, labels[idx] ?? "", pointValues);
      },
      plugins: {
        legend: {
          display: hasData,
          position: "bottom",
          labels: { boxWidth: 10, font: { size: 11 }, color: "rgba(100, 116, 139, 0.95)" },
        },
        tooltip: {
          enabled: hasData,
          mode: "index",
          intersect: false,
          callbacks: {
            title: (items) => labels[items[0]?.dataIndex ?? 0] ?? "",
            label: (ctx) => {
              const dsIndex = typeof ctx.datasetIndex === "number" ? ctx.datasetIndex : 0;
              const entry = series[dsIndex];
              const idx = ctx.dataIndex;
              const y = typeof ctx.parsed.y === "number" && Number.isFinite(ctx.parsed.y) ? ctx.parsed.y : 0;
              if (entry?.tooltipFormat) {
                if (
                  entry.tooltipRawValues &&
                  typeof idx === "number" &&
                  idx >= 0 &&
                  idx < entry.tooltipRawValues.length
                ) {
                  const raw = Number(entry.tooltipRawValues[idx] ?? 0);
                  return `${ctx.dataset.label ?? ""}: ${entry.tooltipFormat(raw)}`;
                }
                return `${ctx.dataset.label ?? ""}: ${entry.tooltipFormat(y)}`;
              }
              const rounded = Math.round(y);
              return `${ctx.dataset.label ?? ""}: ${rounded === y ? rounded : y.toFixed(1)}`;
            },
          },
        },
      },
      scales: {
        x: {
          display: hasData,
          stacked: !isOverlay,
          grid: { display: false },
          ticks: {
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 8,
            color: "rgba(100, 116, 139, 0.9)",
            font: { size: 10 },
          },
          border: { display: false },
        },
        y: {
          display: hasData,
          stacked: !isOverlay,
          beginAtZero: true,
          suggestedMax: maxStack * 1.02,
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          ticks: {
            maxTicksLimit: 5,
            color: "rgba(100, 116, 139, 0.9)",
            font: { size: 10 },
          },
          border: { display: false },
        },
      },
    }),
    [hasData, isOverlay, labels, live, maxStack, onPointClick, series],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">No stacked trend data in this range.</p>;
  }

  const pxHeight = Math.max(96, height);

  return (
    <div className="space-y-2">
      <div
        className="relative w-full"
        style={{ height: pxHeight }}
        role="img"
        aria-label={chartAccessibilityLabel}
      >
        <CanvasLine data={chartData} options={options} />
      </div>
      <div className="flex flex-wrap gap-3">
        {series.map((entry) => {
          const yLast = Number(entry.values[pointCount - 1] ?? 0);
          const rawLatest = entry.tooltipRawValues?.[pointCount - 1];
          const summary =
            typeof rawLatest === "number" && entry.tooltipFormat
              ? entry.tooltipFormat(rawLatest)
              : entry.tooltipFormat
                ? entry.tooltipFormat(yLast)
                : String(Math.round(yLast) === yLast ? Math.round(yLast) : yLast.toFixed(1));
          return (
            <p key={entry.id} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-neutral-300">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
              <span>{entry.label}</span>
              <span className="tabular-nums text-slate-800 dark:text-neutral-100">{summary}</span>
            </p>
          );
        })}
      </div>
      <p className="truncate text-xs text-slate-500 dark:text-neutral-400">
        {labels[0]} {" -> "} {labels[labels.length - 1]}
      </p>
    </div>
  );
}
