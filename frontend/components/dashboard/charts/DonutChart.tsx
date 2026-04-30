"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasDoughnut } from "./chartCanvas";

export type DonutDatum = {
  id: string;
  label: string;
  value: number;
  color: string;
};

export function DonutChart({
  title,
  items,
  centerLabel,
  centerValue,
  onSliceClick,
}: {
  title: string;
  items: DonutDatum[];
  centerLabel?: string;
  centerValue?: string;
  onSliceClick?: (item: DonutDatum) => void;
}) {
  const total = useMemo(() => items.reduce((sum, item) => sum + Math.max(0, item.value), 0), [items]);
  const hasData = total > 0;

  const chartData = useMemo((): ChartData<"doughnut"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"doughnut">[] };
    }
    return {
      labels: items.map((i) => i.label),
      datasets: [
        {
          data: items.map((i) => Math.max(0, i.value)),
          backgroundColor: items.map((i) => i.color),
          borderColor: items.map(() => "rgba(255,255,255,0.06)"),
          borderWidth: 1,
          hoverOffset: 6,
        },
      ],
    };
  }, [hasData, items]);

  const options = useMemo<ChartOptions<"doughnut">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      animation: { duration: hasData ? 450 : 0 },
      onClick: (_event, elements) => {
        if (!hasData || !onSliceClick || !elements.length) {
          return;
        }
        const i = elements[0].index;
        const item = items[i];
        if (item) {
          onSliceClick(item);
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: hasData,
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed;
              const n = typeof v === "number" ? v : 0;
              const pct = total > 0 ? (n / total) * 100 : 0;
              return `${ctx.label}: ${n.toFixed(0)} (${pct.toFixed(1)}%)`;
            },
          },
        },
      },
    }),
    [hasData, items, onSliceClick, total],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-500 dark:text-neutral-400">No data available.</p>;
  }

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="relative mx-auto h-[190px] w-[190px] shrink-0">
        <CanvasDoughnut data={chartData} options={options} />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <p className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-neutral-400">
            {centerLabel ?? title}
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
            {centerValue ?? `${Math.round(total)}`}
          </p>
        </div>
      </div>
      <ul className="space-y-1.5">
        {items.map((item) => {
          const pct = (Math.max(0, item.value) / total) * 100;
          return (
            <li
              key={item.id}
              className={`flex items-center justify-between gap-3 text-xs ${onSliceClick ? "cursor-pointer rounded px-1 py-0.5 hover:bg-slate-100/70 dark:hover:bg-neutral-800/60" : ""}`}
              onClick={onSliceClick ? () => onSliceClick(item) : undefined}
              title={`${item.label}: ${item.value} (${pct.toFixed(1)}%)`}
            >
              <span className="inline-flex items-center gap-2 text-slate-700 dark:text-neutral-300">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                {item.label}
              </span>
              <span className="tabular-nums text-slate-900 dark:text-neutral-100">
                {item.value.toFixed(0)} ({pct.toFixed(1)}%)
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
