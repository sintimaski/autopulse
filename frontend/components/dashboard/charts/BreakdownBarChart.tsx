"use client";

type BreakdownBarDatum = {
  key: string;
  value: number;
  secondaryValue?: number;
  secondaryLabel?: string;
};

type BreakdownBarChartProps = {
  items: BreakdownBarDatum[];
  emptyMessage?: string;
  valueLabel?: string;
  formatPrimaryValue?: (value: number) => string;
  className?: string;
  onItemClick?: (item: BreakdownBarDatum) => void;
};

export function BreakdownBarChart({
  items,
  emptyMessage = "No breakdown data available for this range.",
  valueLabel,
  formatPrimaryValue = (value) => `${Math.round(value)}`,
  className,
  onItemClick,
}: BreakdownBarChartProps) {
  if (!items.length) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">{emptyMessage}</p>;
  }
  let maxValue = 1;
  for (const item of items) {
    if (item.value > maxValue) {
      maxValue = item.value;
    }
  }

  return (
    <ul className={`space-y-2 ${className ?? ""}`}>
      {items.map((item) => {
        const widthPct = Math.max(4, Math.round((item.value / maxValue) * 100));
        return (
          <li
            key={item.key}
            title={`${item.key}: ${formatPrimaryValue(item.value)}${valueLabel ? ` ${valueLabel}` : ""}`}
            onClick={onItemClick ? () => onItemClick(item) : undefined}
            className={onItemClick ? "cursor-pointer rounded-md px-1 py-1 hover:bg-slate-100/70 dark:hover:bg-neutral-800/60" : ""}
          >
            <div className="mb-1 flex items-center justify-between gap-3">
              <p className="min-w-0 truncate font-mono text-xs text-slate-800 dark:text-neutral-100">{item.key}</p>
              <p className="shrink-0 tabular-nums text-xs font-medium text-slate-700 dark:text-neutral-200">
                {formatPrimaryValue(item.value)}
                {valueLabel ? ` ${valueLabel}` : ""}
                {item.secondaryLabel && item.secondaryValue !== undefined
                  ? ` · ${item.secondaryLabel} ${item.secondaryValue.toFixed(1)}%`
                  : ""}
              </p>
            </div>
            <div className="h-2 rounded-full bg-slate-100 dark:bg-neutral-800">
              <div
                className="h-2 rounded-full bg-sky-500/75 dark:bg-sky-400/70"
                style={{ width: `${widthPct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export type { BreakdownBarDatum };
