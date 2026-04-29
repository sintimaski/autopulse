"use client";

type PercentileLadderProps = {
  p50: number;
  p95: number;
  p99: number;
  onRowClick?: (label: "p50" | "p95" | "p99", value: number) => void;
};

function widthPercent(value: number, maxValue: number): number {
  if (maxValue <= 0) {
    return 0;
  }
  return Math.max(3, Math.min(100, (value / maxValue) * 100));
}

export function PercentileLadder({ p50, p95, p99, onRowClick }: PercentileLadderProps) {
  const maxLatency = Math.max(p50, p95, p99, 1);
  const rows: Array<{ label: string; value: number; tone: string }> = [
    { label: "p50", value: p50, tone: "bg-emerald-500/70 dark:bg-emerald-400/65" },
    { label: "p95", value: p95, tone: "bg-amber-500/75 dark:bg-amber-400/70" },
    { label: "p99", value: p99, tone: "bg-rose-500/75 dark:bg-rose-400/70" },
  ];

  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <div
          key={row.label}
          title={`${row.label}: ${row.value.toFixed(1)} ms`}
          onClick={onRowClick ? () => onRowClick(row.label as "p50" | "p95" | "p99", row.value) : undefined}
          className={`grid grid-cols-[42px_1fr_auto] items-center gap-2 ${onRowClick ? "cursor-pointer rounded px-1 py-0.5 hover:bg-slate-100/70 dark:hover:bg-neutral-800/60" : ""}`}
        >
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
            {row.label}
          </span>
          <div className="h-2.5 rounded-full bg-slate-100 dark:bg-neutral-800">
            <div
              className={`h-2.5 rounded-full ${row.tone}`}
              style={{ width: `${widthPercent(row.value, maxLatency)}%` }}
            />
          </div>
          <span className="text-xs tabular-nums text-slate-700 dark:text-neutral-200">
            {row.value.toFixed(1)} ms
          </span>
        </div>
      ))}
      <p className="pt-1 text-xs text-slate-500 dark:text-neutral-400">
        Relative to p99 in current window ({p99.toFixed(1)} ms).
      </p>
    </div>
  );
}
