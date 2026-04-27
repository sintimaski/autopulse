"use client";

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
}: MultiSeriesLineChartProps) {
  const width = 520;
  const hasData = series.some((entry) => entry.values.some((value) => value > 0));
  if (!hasData || !labels.length) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">No status-class data in this range.</p>;
  }
  const maxValue = Math.max(
    1,
    ...series.flatMap((entry) => entry.values).map((value) => Number(value || 0)),
  );

  return (
    <div className="space-y-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-28 w-full">
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
        {labels[0]} {" -> "} {labels[labels.length - 1]}
      </p>
    </div>
  );
}

export type { MultiSeriesLineChartSeries };
