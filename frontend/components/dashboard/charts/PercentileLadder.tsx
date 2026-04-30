"use client";

import { useMemo } from "react";
import type { ChartData, ChartOptions } from "chart.js";

import { CanvasBar } from "./chartCanvas";

type PercentileLadderProps = {
  p50: number;
  p95: number;
  p99: number;
  onRowClick?: (label: "p50" | "p95" | "p99", value: number) => void;
};

const ROW_LABELS = ["p50", "p95", "p99"] as const;

export function PercentileLadder({ p50, p95, p99, onRowClick }: PercentileLadderProps) {
  const maxLatency = Math.max(p50, p95, p99, 1);
  const values = useMemo(() => [p50, p95, p99], [p50, p95, p99]);

  const chartData = useMemo((): ChartData<"bar"> => {
    return {
      labels: [...ROW_LABELS],
      datasets: [
        {
          label: "Latency (ms)",
          data: values,
          backgroundColor: [
            "rgba(16, 185, 129, 0.78)",
            "rgba(245, 158, 11, 0.78)",
            "rgba(244, 63, 94, 0.78)",
          ],
          borderRadius: 4,
          borderSkipped: false,
        },
      ],
    };
  }, [values]);

  const options = useMemo<ChartOptions<"bar">>(
    () => ({
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 350 },
      onClick: (_event, elements) => {
        if (!onRowClick || !elements.length) {
          return;
        }
        const i = elements[0].index;
        const key = ROW_LABELS[i];
        const val = values[i];
        if (key !== undefined && val !== undefined) {
          onRowClick(key, val);
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed.x;
              const n = typeof v === "number" && Number.isFinite(v) ? v : 0;
              return `${n.toFixed(1)} ms`;
            },
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          suggestedMax: maxLatency * 1.02,
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          ticks: {
            color: "rgba(100, 116, 139, 0.9)",
            font: { size: 10 },
            callback: (v) => `${Number(v).toFixed(0)} ms`,
          },
          border: { display: false },
        },
        y: {
          grid: { display: false },
          ticks: {
            color: "rgba(71, 85, 105, 0.95)",
            font: { size: 11, weight: 600 },
          },
          border: { display: false },
        },
      },
    }),
    [maxLatency, onRowClick, values],
  );

  return (
    <div className="space-y-2">
      <div className="relative h-28 w-full">
        <CanvasBar data={chartData} options={options} />
      </div>
      <p className="pt-1 text-xs text-slate-500 dark:text-neutral-400">
        Relative to p99 in current window ({p99.toFixed(1)} ms).
      </p>
    </div>
  );
}
