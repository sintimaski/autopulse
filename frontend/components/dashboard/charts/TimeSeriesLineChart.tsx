"use client";

import { useMemo } from "react";
import type { ChartOptions } from "chart.js";

import { CanvasLine } from "./chartCanvas";

type TimeSeriesLineChartProps = {
  title: string;
  values: number[];
  labels: string[];
  color: string;
  formatValue: (value: number) => string;
  summaryValue?: number;
  summaryLabel?: string;
  emptyMessage?: string;
  /** Tailwind height class for the plot area (default matches compact dashboard cards). */
  chartAreaHeightClass?: string;
  /** When true, Chart.js skips tween on data changes (live polling / in-place updates). */
  live?: boolean;
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
  return `rgba(59, 130, 246, ${alpha})`;
}

export function TimeSeriesLineChart({
  title,
  values,
  labels,
  color,
  formatValue,
  summaryValue,
  summaryLabel = "Latest",
  emptyMessage = "No data for this graph range.",
  chartAreaHeightClass = "h-[5.25rem]",
  live = false,
}: TimeSeriesLineChartProps) {
  const latest = values.length ? values[values.length - 1] : 0;
  const displayValue = summaryValue ?? latest;
  const maxY = useMemo(() => Math.max(1, ...values.map((v) => Number(v) || 0)), [values]);

  const chartData = useMemo(
    () => ({
      labels,
      datasets: [
        {
          label: title,
          data: values,
          borderColor: color,
          backgroundColor: hexToRgba(color, 0.14),
          borderWidth: 2,
          tension: 0.28,
          fill: true,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: color,
          pointHoverBorderColor: "rgba(255,255,255,0.95)",
          pointHoverBorderWidth: 1.5,
        },
      ],
    }),
    [labels, values, title, color],
  );

  const options = useMemo<ChartOptions<"line">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: live || values.length > 120 ? 0 : 400 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          displayColors: false,
          callbacks: {
            title: (items) => {
              const i = items[0]?.dataIndex ?? 0;
              return labels[i] ?? "";
            },
            label: (ctx) => {
              const v = ctx.parsed.y;
              const n = typeof v === "number" && Number.isFinite(v) ? v : 0;
              return `${title}: ${formatValue(n)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 6,
            color: "rgba(100, 116, 139, 0.9)",
            font: { size: 10 },
          },
          border: { display: false },
        },
        y: {
          beginAtZero: true,
          suggestedMax: maxY * 1.06,
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          ticks: {
            maxTicksLimit: 5,
            color: "rgba(100, 116, 139, 0.9)",
            font: { size: 10 },
            callback: (tickValue) => formatValue(Number(tickValue)),
          },
          border: { display: false },
        },
      },
    }),
    [formatValue, labels, live, maxY, title, values],
  );

  return (
    <div className="rounded-xl border border-slate-200/80 bg-gradient-to-br from-white/90 via-slate-50/80 to-indigo-50/60 p-3 dark:border-neutral-700 dark:bg-gradient-to-br dark:from-neutral-900/90 dark:via-neutral-900/80 dark:to-indigo-950/20">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-700 dark:text-neutral-200">{title}</p>
        <div className="text-right">
          <p className="text-xs text-slate-500 dark:text-neutral-400">{summaryLabel}</p>
          <p className="text-xs font-medium tabular-nums text-slate-700 dark:text-neutral-200">
            {formatValue(displayValue)}
          </p>
        </div>
      </div>
      {values.length ? (
        <>
          <div className={`relative w-full ${chartAreaHeightClass}`} aria-label={`${title} time series chart`}>
            <CanvasLine data={chartData} options={options} />
          </div>
          <p className="mt-1 truncate text-xs text-slate-500 dark:text-neutral-400">
            {labels[0]} {" -> "} {labels[labels.length - 1]}
          </p>
        </>
      ) : (
        <p className="text-xs text-slate-500 dark:text-neutral-400">{emptyMessage}</p>
      )}
    </div>
  );
}
