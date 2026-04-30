"use client";

import { useMemo } from "react";
import type { ChartData, ChartDataset, ChartOptions } from "chart.js";

import { CanvasScatter } from "./chartCanvas";

export type ScatterPlotPoint = {
  id: string;
  x: number;
  y: number;
  label: string;
  tone?: "neutral" | "warning" | "danger";
};

type ScatterPlotChartProps = {
  points: ScatterPlotPoint[];
  xLabel: string;
  yLabel: string;
  emptyMessage?: string;
  onPointClick?: (point: ScatterPlotPoint) => void;
};

function toneColor(tone: ScatterPlotPoint["tone"]): string {
  if (tone === "danger") {
    return "#f43f5e";
  }
  if (tone === "warning") {
    return "#f59e0b";
  }
  return "#38bdf8";
}

export function ScatterPlotChart({
  points,
  xLabel,
  yLabel,
  emptyMessage = "No scatter data in this range.",
  onPointClick,
}: ScatterPlotChartProps) {
  const hasData = points.length > 0;

  const { maxX, maxY } = useMemo(() => {
    if (!hasData) {
      return { maxX: 1, maxY: 1 };
    }
    let mx = 1;
    let my = 1;
    for (const point of points) {
      const x = Math.max(0, point.x);
      const y = Math.max(0, point.y);
      if (x > mx) {
        mx = x;
      }
      if (y > my) {
        my = y;
      }
    }
    return { maxX: mx, maxY: my };
  }, [hasData, points]);

  const chartData = useMemo((): ChartData<"scatter"> => {
    if (!hasData) {
      return { datasets: [] as ChartDataset<"scatter">[] };
    }
    return {
      datasets: [
        {
          label: "Points",
          data: points.map((p) => ({ x: p.x, y: p.y })),
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: points.map((p) => toneColor(p.tone)),
          pointBorderColor: "#ffffff",
          pointBorderWidth: 1,
        },
      ],
    };
  }, [hasData, points]);

  const options = useMemo<ChartOptions<"scatter">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: hasData ? 400 : 0 },
      onClick: (_event, elements) => {
        if (!hasData || !onPointClick || !elements.length) {
          return;
        }
        const i = elements[0].index;
        const p = points[i];
        if (p) {
          onPointClick(p);
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: hasData,
          callbacks: {
            title: () => "",
            label: (ctx) => {
              const i = ctx.dataIndex;
              return points[i]?.label ?? "";
            },
          },
        },
      },
      scales: {
        x: {
          display: hasData,
          type: "linear",
          beginAtZero: true,
          suggestedMax: maxX * 1.05,
          title: { display: hasData, text: xLabel, color: "rgba(100,116,139,0.95)", font: { size: 11 } },
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          ticks: { color: "rgba(100, 116, 139, 0.9)", font: { size: 10 } },
          border: { display: false },
        },
        y: {
          display: hasData,
          type: "linear",
          beginAtZero: true,
          suggestedMax: maxY * 1.08,
          title: { display: hasData, text: yLabel, color: "rgba(100,116,139,0.95)", font: { size: 11 } },
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          ticks: { color: "rgba(100, 116, 139, 0.9)", font: { size: 10 } },
          border: { display: false },
        },
      },
    }),
    [hasData, maxX, maxY, onPointClick, points, xLabel, yLabel],
  );

  if (!hasData) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-2">
      <div className="relative h-44 w-full">
        <CanvasScatter data={chartData} options={options} />
      </div>
    </div>
  );
}
