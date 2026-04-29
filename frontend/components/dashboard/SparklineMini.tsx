"use client";

import { useState } from "react";

export function SparklineMini({
  values,
  colorClass,
  labels,
  onPointClick,
}: {
  values: number[];
  colorClass?: string;
  labels?: string[];
  onPointClick?: (index: number, value: number) => void;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  if (values.length === 0) {
    return <div className="h-8 w-full rounded bg-slate-100 dark:bg-neutral-800" />;
  }
  let max = 1;
  for (const value of values) {
    if (value > max) {
      max = value;
    }
  }
  const points = values
    .map((value, index) => `${(index / Math.max(values.length - 1, 1)) * 100},${100 - (value / max) * 100}`)
    .join(" ");
  const active = hoverIndex ?? values.length - 1;
  return (
    <div>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="h-8 w-full cursor-crosshair"
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
          const idx = Math.round(ratio * Math.max(values.length - 1, 0));
          setHoverIndex(idx);
        }}
        onMouseLeave={() => setHoverIndex(null)}
        onClick={() => onPointClick?.(active, values[active] ?? 0)}
      >
        <title>{labels?.[active] ? `${labels[active]}: ${values[active] ?? 0}` : `${values[active] ?? 0}`}</title>
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          points={points}
          className={colorClass ?? "text-sky-600 dark:text-sky-300"}
        />
      </svg>
      {hoverIndex !== null ? (
        <p className="mt-1 truncate text-[11px] text-slate-500 dark:text-neutral-400">
          {labels?.[hoverIndex] ? `${labels[hoverIndex]} · ` : ""}
          {values[hoverIndex] ?? 0}
        </p>
      ) : null}
    </div>
  );
}
