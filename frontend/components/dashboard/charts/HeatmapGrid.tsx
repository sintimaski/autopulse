"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions, ScriptableContext } from "chart.js";

import { CanvasBar } from "./chartCanvas";

export type HeatmapCell = {
  x: string;
  y: string;
  value: number;
};

function colorForValue(value: number, max: number): string {
  const ratio = max > 0 ? value / max : 0;
  if (ratio >= 0.75) {
    return "rgba(244, 63, 94, 0.88)";
  }
  if (ratio >= 0.5) {
    return "rgba(251, 113, 133, 0.82)";
  }
  if (ratio >= 0.25) {
    return "rgba(251, 191, 36, 0.82)";
  }
  if (ratio > 0) {
    return "rgba(148, 163, 184, 0.75)";
  }
  return "rgba(241, 245, 249, 0.55)";
}

export function HeatmapGrid({
  cells,
  xLabels,
  yLabels,
  onCellClick,
}: {
  cells: HeatmapCell[];
  xLabels: string[];
  yLabels: string[];
  onCellClick?: (cell: HeatmapCell) => void;
}) {
  const hasData = Boolean(cells.length && xLabels.length && yLabels.length);

  const lookup = useMemo(() => {
    if (!hasData) {
      return new Map<string, number>();
    }
    return new Map(cells.map((cell) => [`${cell.x}|${cell.y}`, cell.value] as const));
  }, [cells, hasData]);

  const max = useMemo(() => {
    if (!hasData) {
      return 1;
    }
    return Math.max(1, ...cells.map((c) => c.value));
  }, [cells, hasData]);

  const chartData = useMemo((): ChartData<"bar"> => {
    if (!hasData) {
      return { labels: [], datasets: [] as ChartDataset<"bar">[] };
    }
    return {
      labels: yLabels,
      datasets: xLabels.map((xLabel) => ({
        label: xLabel,
        data: yLabels.map((yLabel) => lookup.get(`${xLabel}|${yLabel}`) ?? 0),
        backgroundColor: (ctx: ScriptableContext<"bar">) => {
          const v = Number(ctx.raw ?? 0);
          return colorForValue(v, max);
        },
        borderRadius: 2,
        borderWidth: 1,
        borderColor: "rgba(15, 23, 42, 0.06)",
      })) as ChartDataset<"bar">[],
    };
  }, [hasData, lookup, max, xLabels, yLabels]);

  const options = useMemo<ChartOptions<"bar">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: hasData ? 300 : 0 },
      onClick: (_event, elements) => {
        if (!hasData || !onCellClick || !elements.length) {
          return;
        }
        const { datasetIndex, index } = elements[0];
        const x = xLabels[datasetIndex];
        const y = yLabels[index];
        if (x === undefined || y === undefined) {
          return;
        }
        const value = lookup.get(`${x}|${y}`) ?? 0;
        onCellClick({ x, y, value });
      },
      plugins: {
        legend: {
          display: hasData,
          position: "top",
          labels: { boxWidth: 10, font: { size: 10 }, color: "rgba(100, 116, 139, 0.95)" },
        },
        tooltip: {
          enabled: hasData,
          mode: "index",
          intersect: false,
          callbacks: {
            title: (items) => {
              const row = yLabels[items[0]?.dataIndex ?? 0];
              return row ?? "";
            },
            label: (ctx) => {
              const v = ctx.parsed.y;
              const n = typeof v === "number" && Number.isFinite(v) ? v : 0;
              return `${ctx.dataset.label ?? ""}: ${n}`;
            },
          },
        },
      },
      scales: {
        x: {
          display: hasData,
          stacked: false,
          grid: { display: false },
          ticks: { color: "rgba(100, 116, 139, 0.9)", font: { size: 10 } },
          border: { display: false },
        },
        y: {
          display: hasData,
          stacked: false,
          grid: { color: "rgba(100, 116, 139, 0.08)" },
          ticks: {
            color: "rgba(71, 85, 105, 0.95)",
            font: { size: 10 },
            autoSkip: false,
          },
          border: { display: false },
        },
      },
    }),
    [hasData, lookup, onCellClick, xLabels, yLabels],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-500 dark:text-neutral-400">No heatmap data available.</p>;
  }

  const h = Math.max(200, 48 + yLabels.length * 28);

  return (
    <div className="overflow-x-auto">
      <div className="relative min-w-[280px]" style={{ height: h }}>
        <CanvasBar data={chartData} options={options} />
      </div>
    </div>
  );
}
