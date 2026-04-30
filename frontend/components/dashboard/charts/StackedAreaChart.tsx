"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasLine } from "./chartCanvas";

export type StackedAreaSeries = {
  id: string;
  label: string;
  color: string;
  values: number[];
};

type StackedAreaChartProps = {
  labels: string[];
  series: StackedAreaSeries[];
  height?: number;
  onPointClick?: (index: number, label: string, values: Record<string, number>) => void;
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
  onPointClick,
}: StackedAreaChartProps) {
  const hasData = useMemo(() => Boolean(labels.length && series.length), [labels.length, series.length]);

  const pointCount = labels.length;
  const maxStack = useMemo(
    () =>
      hasData
        ? Math.max(
            1,
            ...Array.from({ length: pointCount }, (_, idx) =>
              series.reduce((sum, entry) => sum + Math.max(0, Number(entry.values[idx] ?? 0)), 0),
            ),
          )
        : 1,
    [hasData, pointCount, series],
  );

  const chartData = useMemo((): ChartData<"line"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"line">[] };
    }
    return {
      labels,
      datasets: series.map((entry) => ({
        label: entry.label,
        data: entry.values.map((v) => Math.max(0, Number(v ?? 0))),
        borderColor: entry.color,
        backgroundColor: hexToRgba(entry.color, 0.32),
        borderWidth: 1.5,
        tension: 0.25,
        fill: true,
        stack: "stack0",
        pointRadius: 0,
        pointHoverRadius: 3,
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
          stacked: true,
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
          stacked: true,
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
    [hasData, labels, maxStack, onPointClick, series],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">No stacked trend data in this range.</p>;
  }

  const pxHeight = Math.max(96, height);

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
              {Math.round(Number(entry.values[pointCount - 1] ?? 0))}
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
