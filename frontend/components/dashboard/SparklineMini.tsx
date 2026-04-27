"use client";

export function SparklineMini({ values, colorClass }: { values: number[]; colorClass?: string }) {
  if (values.length === 0) {
    return <div className="h-8 w-full rounded bg-slate-100 dark:bg-neutral-800" />;
  }
  const max = Math.max(...values, 1);
  const points = values
    .map((value, index) => `${(index / Math.max(values.length - 1, 1)) * 100},${100 - (value / max) * 100}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-8 w-full">
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        points={points}
        className={colorClass ?? "text-sky-600 dark:text-sky-300"}
      />
    </svg>
  );
}
