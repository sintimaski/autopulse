"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasLine } from "./chartCanvas";
import { ChartScopeTintOverlay } from "./ChartScopeTintOverlay";

export type MultiSeriesLineChartSeries = {
  id: string;
  label: string;
  color: string;
  values: number[];
  /** When chart Y uses a transform (e.g. normalized), tooltips/footer can show raw using this. */
  tooltipRawValues?: number[];
  tooltipFormat?: (raw: number) => string;
};

type MultiSeriesLineChartProps = {
  labels: string[];
  series: MultiSeriesLineChartSeries[];
  height?: number;
  /** Cap Y-axis suggested max (e.g. 100 for %-style charts). */
  ySuggestedMaxCap?: number;
  /** >0 shows points (helps sparse / per-sample series where lines are hard to see). */
  pointRadius?: number;
  emptyMessage?: string;
  onPointClick?: (index: number, label: string, values: Record<string, number>) => void;
  /** Skip Chart.js tween on data updates (live dashboard refresh). */
  live?: boolean;
  chartsScopePending?: boolean;
};

export function MultiSeriesLineChart({
  labels,
  series,
  height = 110,
  ySuggestedMaxCap,
  pointRadius = 0,
  emptyMessage = "No series data in this range.",
  onPointClick,
  live = false,
  chartsScopePending = false,
}: MultiSeriesLineChartProps) {
  const hasData = useMemo(() => Boolean(labels.length && series.length), [labels.length, series.length]);

  const maxValue = useMemo(
    () =>
      hasData
        ? Math.max(
            1,
            ...series
              .flatMap((entry) => entry.values)
              .map((value) => Number(value))
              .filter((value) => Number.isFinite(value)),
          )
        : 1,
    [hasData, series],
  );

  const ySuggestedMax = useMemo(() => {
    const raw = maxValue * 1.05;
    if (typeof ySuggestedMaxCap === "number" && Number.isFinite(ySuggestedMaxCap)) {
      return Math.min(ySuggestedMaxCap, Math.max(raw, 1));
    }
    return raw;
  }, [maxValue, ySuggestedMaxCap]);

  const chartData = useMemo((): ChartData<"line"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"line">[] };
    }
    return {
      labels,
      datasets: series.map((entry) => ({
        label: entry.label,
        data: entry.values.map((v) => (typeof v === "number" && Number.isFinite(v) ? v : null)),
        borderColor: entry.color,
        backgroundColor: "transparent",
        borderWidth: 2,
        tension: 0.22,
        pointRadius,
        pointHoverRadius: 4,
        pointHoverBorderWidth: 1,
      })) as ChartDataset<"line">[],
    };
  }, [hasData, labels, pointRadius, series]);

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
        const label = labels[idx] ?? "";
        const valuesAt: Record<string, number> = {};
        for (const entry of series) {
          const raw = entry.values[idx];
          valuesAt[entry.id] = typeof raw === "number" && Number.isFinite(raw) ? raw : 0;
        }
        onPointClick(idx, label, valuesAt);
      },
      plugins: {
        legend: {
          display: hasData,
          position: "bottom",
          labels: {
            boxWidth: 10,
            font: { size: 11 },
            color: "rgba(100, 116, 139, 0.95)",
          },
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
              if (ctx.parsed.y === null || !Number.isFinite(ctx.parsed.y as number)) {
                return `${ctx.dataset.label ?? ""}: —`;
              }
              const y = ctx.parsed.y as number;
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
              const n = y;
              return `${ctx.dataset.label ?? ""}: ${Math.round(n) === n ? Math.round(n) : n.toFixed(1)}`;
            },
          },
        },
      },
      scales: {
        x: {
          display: hasData,
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
          beginAtZero: true,
          suggestedMax: ySuggestedMax,
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
    [hasData, labels, live, onPointClick, series, ySuggestedMax],
  );

  if (!hasData) {
    return (
      <div className="relative min-h-[5rem]">
        {chartsScopePending ? <ChartScopeTintOverlay className="rounded-lg" /> : null}
        <p className="relative z-0 text-sm text-slate-600 dark:text-neutral-300">{emptyMessage}</p>
      </div>
    );
  }

  const pxHeight = Math.max(80, height);

  return (
    <div className="space-y-2">
      <div className="relative w-full overflow-hidden rounded-lg" style={{ height: pxHeight }}>
        {chartsScopePending ? <ChartScopeTintOverlay className="rounded-lg" /> : null}
        <div className="relative z-0 h-full w-full">
          <CanvasLine data={chartData} options={options} />
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        {series.map((entry) => {
          const lastIdx = entry.values.length - 1;
          let yLast = 0;
          let lastFiniteIdx = -1;
          for (let i = lastIdx; i >= 0; i--) {
            const v = entry.values[i];
            if (typeof v === "number" && Number.isFinite(v)) {
              yLast = v;
              lastFiniteIdx = i;
              break;
            }
          }
          const rawLast =
            lastFiniteIdx >= 0 ? entry.tooltipRawValues?.[lastFiniteIdx] : undefined;
          const summary =
            typeof rawLast === "number" && entry.tooltipFormat
              ? entry.tooltipFormat(rawLast)
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
