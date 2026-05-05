"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasBar } from "./chartCanvas";

export type BreakdownBarDatum = {
  key: string;
  value: number;
  secondaryValue?: number;
  secondaryLabel?: string;
};

type BreakdownBarChartProps = {
  items: BreakdownBarDatum[];
  emptyMessage?: string;
  valueLabel?: string;
  formatPrimaryValue?: (value: number) => string;
  className?: string;
  onItemClick?: (item: BreakdownBarDatum) => void;
  /** Skip Chart.js tween on data updates (live dashboard refresh). */
  live?: boolean;
};

export function BreakdownBarChart({
  items,
  emptyMessage = "No breakdown data available for this range.",
  valueLabel,
  formatPrimaryValue = (value) => `${Math.round(value)}`,
  className,
  onItemClick,
  live = false,
}: BreakdownBarChartProps) {
  const hasData = items.length > 0;
  const maxValue = useMemo(
    () => (hasData ? Math.max(1, ...items.map((i) => i.value)) : 1),
    [hasData, items],
  );

  const chartData = useMemo((): ChartData<"bar"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"bar">[] };
    }
    return {
      labels: items.map((i) => i.key),
      datasets: [
        {
          label: valueLabel ?? "value",
          data: items.map((i) => i.value),
          backgroundColor: "rgba(56, 189, 248, 0.72)",
          borderRadius: 4,
          borderSkipped: false,
        },
      ],
    };
  }, [hasData, items, valueLabel]);

  const options = useMemo<ChartOptions<"bar">>(
    () => ({
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: live ? 0 : hasData ? 350 : 0 },
      onClick: (_event, elements) => {
        if (!hasData || !onItemClick || !elements.length) {
          return;
        }
        const i = elements[0].index;
        const item = items[i];
        if (item) {
          onItemClick(item);
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: hasData,
          callbacks: {
            title: (ctx) => ctx[0]?.label ?? "",
            label: (ctx) => {
              const item = items[ctx.dataIndex];
              if (!item) {
                return "";
              }
              const primary = formatPrimaryValue(item.value) + (valueLabel ? ` ${valueLabel}` : "");
              if (item.secondaryLabel !== undefined && item.secondaryValue !== undefined) {
                return `${primary} · ${item.secondaryLabel} ${item.secondaryValue.toFixed(1)}%`;
              }
              return primary;
            },
          },
        },
      },
      scales: {
        x: {
          display: hasData,
          beginAtZero: true,
          suggestedMax: maxValue * 1.02,
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          ticks: {
            color: "rgba(100, 116, 139, 0.9)",
            font: { size: 10 },
            callback: (v) => formatPrimaryValue(Number(v)),
          },
          border: { display: false },
        },
        y: {
          display: hasData,
          grid: { display: false },
          ticks: {
            color: "rgba(51, 65, 85, 0.95)",
            font: { size: 10, family: "ui-monospace, monospace" },
            autoSkip: false,
          },
          border: { display: false },
        },
      },
    }),
    [formatPrimaryValue, hasData, items, live, maxValue, onItemClick, valueLabel],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">{emptyMessage}</p>;
  }

  const chartHeight = Math.max(120, items.length * 36);

  return (
    <div className={`relative w-full ${className ?? ""}`} style={{ height: chartHeight }}>
      <CanvasBar data={chartData} options={options} />
    </div>
  );
}
