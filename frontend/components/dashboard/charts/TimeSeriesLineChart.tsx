"use client";

import { useRef, useState } from "react";

function makeTrendPoints(values: number[], width: number, height: number): string {
  if (values.length === 0) {
    return "";
  }
  const max = Math.max(...values, 1);
  const stepX = values.length > 1 ? width / (values.length - 1) : width / 2;
  return values
    .map((value, idx) => {
      const x = values.length > 1 ? idx * stepX : width / 2;
      const y = height - (value / max) * height;
      return `${x},${Number.isFinite(y) ? y : height}`;
    })
    .join(" ");
}

type TimeSeriesLineChartProps = {
  title: string;
  values: number[];
  labels: string[];
  color: string;
  formatValue: (value: number) => string;
  summaryValue?: number;
  summaryLabel?: string;
  emptyMessage?: string;
};

export function TimeSeriesLineChart({
  title,
  values,
  labels,
  color,
  formatValue,
  summaryValue,
  summaryLabel = "Latest",
  emptyMessage = "No data for this graph range.",
}: TimeSeriesLineChartProps) {
  const width = 260;
  const height = 56;
  const points = makeTrendPoints(values, width, height);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const latest = values.length ? values[values.length - 1] : 0;
  const displayValue = summaryValue ?? latest;
  const maxValue = Math.max(...values, 1);
  const activeIndex = hoverIndex ?? (values.length ? values.length - 1 : null);
  const activeValue = activeIndex === null ? 0 : values[activeIndex] ?? 0;
  const activeLabel = activeIndex === null ? "" : labels[activeIndex] ?? "";
  const activeX =
    activeIndex === null
      ? 0
      : values.length > 1
        ? (activeIndex / (values.length - 1)) * width
        : width / 2;
  const activeY = height - (activeValue / maxValue) * height;

  const onSvgMove = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!values.length || !svgRef.current) {
      return;
    }
    const rect = svgRef.current.getBoundingClientRect();
    if (rect.width <= 0) {
      return;
    }
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const idx = Math.round(ratio * Math.max(values.length - 1, 0));
    setHoverIndex(idx);
  };

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
          <svg
            ref={svgRef}
            viewBox={`0 0 ${width} ${height}`}
            className="h-14 w-full cursor-crosshair"
            onMouseMove={onSvgMove}
            onMouseLeave={() => setHoverIndex(null)}
          >
            <polyline
              points={points}
              fill="none"
              stroke={color}
              strokeWidth={2.25}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {activeIndex !== null ? (
              <circle
                cx={activeX}
                cy={Number.isFinite(activeY) ? activeY : height}
                r={3}
                fill={color}
                stroke="white"
                strokeWidth={1.2}
              />
            ) : null}
          </svg>
          <p className="mt-1 truncate text-xs text-slate-500 dark:text-neutral-400">
            {activeLabel ? `${activeLabel} • ${formatValue(activeValue)}` : null}
          </p>
          <p className="truncate text-xs text-slate-500 dark:text-neutral-400">
            {labels[0]} {" -> "} {labels[labels.length - 1]}
          </p>
        </>
      ) : (
        <p className="text-xs text-slate-500 dark:text-neutral-400">{emptyMessage}</p>
      )}
    </div>
  );
}
