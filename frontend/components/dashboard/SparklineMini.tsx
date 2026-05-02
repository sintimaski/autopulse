"use client";

import { useState } from "react";

export function SparklineMini({
  values,
  colorClass,
  labels,
  onPointClick,
  svgClassName,
  /** When false, no hover scrubbing or crosshair cursor (static sparkline). */
  interactive = true,
}: {
  values: number[];
  colorClass?: string;
  labels?: string[];
  onPointClick?: (index: number, value: number) => void;
  /** Tailwind height/width for the SVG (default h-8). Use e.g. h-3 for a compact strip. */
  svgClassName?: string;
  interactive?: boolean;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const heightClass = (svgClassName ?? "h-8").split(/\s+/).find((c) => c.startsWith("h-")) ?? "h-8";
  if (values.length === 0) {
    return <div className={`${heightClass} w-full rounded bg-slate-100 dark:bg-neutral-800`} />;
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
  const lastIndex = values.length - 1;
  const active = interactive ? (hoverIndex ?? lastIndex) : lastIndex;
  const svgCursor = interactive ? "cursor-crosshair" : "cursor-default";
  return (
    <div>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className={`${svgClassName ?? "h-8 w-full"} ${svgCursor}`}
        onMouseMove={
          interactive
            ? (event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
                const idx = Math.round(ratio * Math.max(values.length - 1, 0));
                setHoverIndex(idx);
              }
            : undefined
        }
        onMouseLeave={interactive ? () => setHoverIndex(null) : undefined}
        onClick={interactive ? () => onPointClick?.(active, values[active] ?? 0) : undefined}
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
      {interactive && hoverIndex !== null ? (
        <p className="mt-1 truncate text-[11px] text-slate-500 dark:text-neutral-400">
          {labels?.[hoverIndex] ? `${labels[hoverIndex]} · ` : ""}
          {values[hoverIndex] ?? 0}
        </p>
      ) : null}
    </div>
  );
}
