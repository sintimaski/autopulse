"use client";

type DonutDatum = {
  id: string;
  label: string;
  value: number;
  color: string;
};

export function DonutChart({
  title,
  items,
  centerLabel,
  centerValue,
  onSliceClick,
}: {
  title: string;
  items: DonutDatum[];
  centerLabel?: string;
  centerValue?: string;
  onSliceClick?: (item: DonutDatum) => void;
}) {
  const total = items.reduce((sum, item) => sum + Math.max(0, item.value), 0);
  if (total <= 0) {
    return <p className="text-sm text-slate-500 dark:text-neutral-400">No data available.</p>;
  }

  const size = 190;
  const radius = 74;
  const stroke = 24;
  const circumference = 2 * Math.PI * radius;
  const segments = items.reduce<
    Array<{ id: string; color: string; dash: number; offset: number; item: DonutDatum }>
  >((acc, item) => {
    const consumed = acc.reduce((sum, segment) => sum + segment.dash, 0);
    const ratio = Math.max(0, item.value) / total;
    const dash = ratio * circumference;
    acc.push({
      id: item.id,
      color: item.color,
      dash,
      offset: -consumed,
      item,
    });
    return acc;
  }, []);

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="relative mx-auto h-[190px] w-[190px] shrink-0">
        <svg viewBox={`0 0 ${size} ${size}`} className="h-[190px] w-[190px] -rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(148,163,184,0.22)"
            strokeWidth={stroke}
          />
          {segments.map((segment) => (
              <circle
                key={segment.id}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={segment.color}
                strokeWidth={stroke}
                strokeDasharray={`${segment.dash} ${circumference - segment.dash}`}
                strokeDashoffset={segment.offset}
                strokeLinecap="butt"
                onClick={onSliceClick ? () => onSliceClick(segment.item) : undefined}
                className={onSliceClick ? "cursor-pointer" : undefined}
              >
                <title>{`${segment.item.label}: ${segment.item.value}`}</title>
              </circle>
          ))}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <p className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-neutral-400">
            {centerLabel ?? title}
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
            {centerValue ?? `${Math.round(total)}`}
          </p>
        </div>
      </div>
      <ul className="space-y-1.5">
        {items.map((item) => {
          const pct = (Math.max(0, item.value) / total) * 100;
          return (
            <li
              key={item.id}
              className={`flex items-center justify-between gap-3 text-xs ${onSliceClick ? "cursor-pointer rounded px-1 py-0.5 hover:bg-slate-100/70 dark:hover:bg-neutral-800/60" : ""}`}
              onClick={onSliceClick ? () => onSliceClick(item) : undefined}
              title={`${item.label}: ${item.value} (${pct.toFixed(1)}%)`}
            >
              <span className="inline-flex items-center gap-2 text-slate-700 dark:text-neutral-300">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                {item.label}
              </span>
              <span className="tabular-nums text-slate-900 dark:text-neutral-100">
                {item.value.toFixed(0)} ({pct.toFixed(1)}%)
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export type { DonutDatum };
