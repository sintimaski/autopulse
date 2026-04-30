"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasLine } from "./chartCanvas";

export type MultiSeriesLineChartSeries = {
  id: string;
  label: string;
  color: string;
  values: number[];
};

type MultiSeriesLineChartProps = {
  labels: string[];
  series: MultiSeriesLineChartSeries[];
  height?: number;
  onPointClick?: (index: number, label: string, values: Record<string, number>) => void;
};

export function MultiSeriesLineChart({
  labels,
  series,
  height = 110,
  onPointClick,
}: MultiSeriesLineChartProps) {
  const hasData = useMemo(
    () => Boolean(labels.length && series.some((entry) => entry.values.some((value) => value > 0))),
    [labels.length, series],
  );

  const maxValue = useMemo(
    () =>
      hasData
        ? Math.max(1, ...series.flatMap((entry) => entry.values).map((value) => Number(value || 0)))
        : 1,
    [hasData, series],
  );

  const chartData = useMemo((): ChartData<"line"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"line">[] };
    }
    return {
      labels,
      datasets: series.map((entry) => ({
        label: entry.label,
        data: entry.values,
        borderColor: entry.color,
        backgroundColor: "transparent",
        borderWidth: 2,
        tension: 0.22,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBorderWidth: 1,
      })) as ChartDataset<"line">[],
    };
  }, [hasData, labels, series]);

  const options = useMemo<ChartOptions<"line">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: !hasData || labels.length > 120 ? 0 : 400 },
      interaction: { mode: "index", intersect: false },
      onClick: (_event, elements) => {
        if (!hasData || !onPointClick || !elements.length) {
          return;
        }
        const idx = elements[0].index;
        const label = labels[idx] ?? "";
        const valuesAt: Record<string, number> = {};
        for (const entry of series) {
          valuesAt[entry.id] = Number(entry.values[idx] ?? 0);
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
              const v = ctx.parsed.y;
              const n = typeof v === "number" && Number.isFinite(v) ? v : 0;
              return `${ctx.dataset.label ?? ""}: ${Math.round(n)}`;
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
          suggestedMax: maxValue * 1.05,
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
    [hasData, labels, maxValue, onPointClick, series],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">No status-class data in this range.</p>;
  }

  const pxHeight = Math.max(80, height);

  return (
    <div className="space-y-2">
      <div className="relative w-full" style={{ height: pxHeight }}>
        <CanvasLine data={chartData} options={options} />
      </div>
      <div className="flex flex-wrap gap-3">
        {series.map((entry) => (
          <p key={entry.id} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-neutral-300">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
            <span>{entry.label}</span>
            <span className="tabular-nums text-slate-800 dark:text-neutral-100">
              {Math.round(entry.values[entry.values.length - 1] ?? 0)}
            </span>
          </p>
        ))}
      </div>
      <p className="truncate text-xs text-slate-500 dark:text-neutral-400">
        {labels[0]} {" -> "} {labels[labels.length - 1]}
      </p>
    </div>
  );
}
