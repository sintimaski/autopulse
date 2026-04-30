"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasBar } from "./chartCanvas";

export type HistogramBucket = {
  label: string;
  count: number;
};

const DEFAULT_BAR = "rgba(14, 165, 233, 0.78)";

export function HistogramChart({
  buckets,
  barColor,
  onBucketClick,
}: {
  buckets: HistogramBucket[];
  /** Pass a hex/rgb string for bar fill; Tailwind class strings fall back to default sky. */
  barColor?: string;
  onBucketClick?: (bucket: HistogramBucket) => void;
}) {
  const hasData = buckets.length > 0;

  const fill =
    barColor && (barColor.startsWith("#") || barColor.startsWith("rgb")) ? barColor : DEFAULT_BAR;

  const chartData = useMemo((): ChartData<"bar"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"bar">[] };
    }
    return {
      labels: buckets.map((b) => b.label),
      datasets: [
        {
          label: "Count",
          data: buckets.map((b) => b.count),
          backgroundColor: fill,
          borderRadius: 4,
          borderSkipped: false,
        },
      ],
    };
  }, [buckets, fill, hasData]);

  const options = useMemo<ChartOptions<"bar">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: hasData ? 350 : 0 },
      onClick: (_event, elements) => {
        if (!hasData || !onBucketClick || !elements.length) {
          return;
        }
        const i = elements[0].index;
        const b = buckets[i];
        if (b) {
          onBucketClick(b);
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: hasData,
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed.y;
              const n = typeof v === "number" && Number.isFinite(v) ? v : 0;
              return `${n} requests`;
            },
          },
        },
      },
      scales: {
        x: {
          display: hasData,
          grid: { display: false },
          ticks: { color: "rgba(100, 116, 139, 0.95)", font: { size: 10 } },
          border: { display: false },
        },
        y: {
          display: hasData,
          beginAtZero: true,
          ticks: { color: "rgba(100, 116, 139, 0.9)", font: { size: 10 } },
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          border: { display: false },
        },
      },
    }),
    [buckets, hasData, onBucketClick],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-500 dark:text-neutral-400">No distribution data available.</p>;
  }

  return (
    <div className="relative min-h-[10rem] w-full">
      <CanvasBar data={chartData} options={options} />
    </div>
  );
}
