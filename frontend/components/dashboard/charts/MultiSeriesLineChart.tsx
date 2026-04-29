"use client";

import { useState } from "react";

type MultiSeriesLineChartSeries = {
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

function makePoints(values: number[], width: number, height: number, maxValue: number): string {
  if (!values.length) {
    return "";
  }
  const stepX = values.length > 1 ? width / (values.length - 1) : width / 2;
  return values
    .map((value, idx) => {
      const x = values.length > 1 ? idx * stepX : width / 2;
      const y = height - (Math.max(0, value) / Math.max(1, maxValue)) * height;
      return `${x},${Number.isFinite(y) ? y : height}`;
    })
    .join(" ");
}

export function MultiSeriesLineChart({
  labels,
  series,
  height = 110,
  onPointClick,
}: MultiSeriesLineChartProps) {
  const width = 520;
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const hasData = series.some((entry) => entry.values.some((value) => value > 0));
  if (!hasData || !labels.length) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">No status-class data in this range.</p>;
  }
  const maxValue = Math.max(
    1,
    ...series.flatMap((entry) => entry.values).map((value) => Number(value || 0)),
  );

  const activeIndex = hoverIndex ?? labels.length - 1;
  const activeLabel = labels[activeIndex] ?? "";
  const activeValues = series.reduce<Record<string, number>>((acc, entry) => {
    acc[entry.id] = entry.values[activeIndex] ?? 0;
    return acc;
  }, {});

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-28 w-full cursor-crosshair"
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
          const idx = Math.round(ratio * Math.max(labels.length - 1, 0));
          setHoverIndex(idx);
        }}
        onMouseLeave={() => setHoverIndex(null)}
        onClick={() => {
          if (!onPointClick) return;
          onPointClick(activeIndex, activeLabel, activeValues);
        }}
      >
        <title>
          {`${activeLabel} · ${series.map((s) => `${s.label}: ${Math.round(activeValues[s.id] ?? 0)}`).join(" · ")}`}
        </title>
        {series.map((entry) => (
          <polyline
            key={entry.id}
            points={makePoints(entry.values, width, height, maxValue)}
            fill="none"
            stroke={entry.color}
            strokeWidth={2.1}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
      </svg>
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
        {activeLabel
          ? `${activeLabel} • ${series
              .map((entry) => `${entry.label} ${Math.round(activeValues[entry.id] ?? 0)}`)
              .join(" · ")}`
          : `${labels[0]} -> ${labels[labels.length - 1]}`}
      </p>
    </div>
  );
}

export type { MultiSeriesLineChartSeries };
