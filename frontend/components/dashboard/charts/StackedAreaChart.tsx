"use client";

type StackedAreaSeries = {
  id: string;
  label: string;
  color: string;
  values: number[];
};

type StackedAreaChartProps = {
  labels: string[];
  series: StackedAreaSeries[];
  height?: number;
  onPointClick?: (index: number, label: string, values: Record<string, number>) => void;
};

export function StackedAreaChart({
  labels,
  series,
  height = 124,
  onPointClick,
}: StackedAreaChartProps) {
  const width = 560;
  if (!labels.length || !series.length) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">No stacked trend data in this range.</p>;
  }
  const pointCount = labels.length;
  const maxStack = Math.max(
    1,
    ...Array.from({ length: pointCount }, (_, idx) =>
      series.reduce((sum, entry) => sum + Math.max(0, Number(entry.values[idx] ?? 0)), 0),
    ),
  );
  const stepX = pointCount > 1 ? width / (pointCount - 1) : width / 2;

  const cumulativeAt = (index: number, seriesIndex: number) =>
    series
      .slice(0, seriesIndex + 1)
      .reduce((sum, entry) => sum + Math.max(0, Number(entry.values[index] ?? 0)), 0);
  const cumulativeBelow = (index: number, seriesIndex: number) =>
    series
      .slice(0, seriesIndex)
      .reduce((sum, entry) => sum + Math.max(0, Number(entry.values[index] ?? 0)), 0);
  const toY = (value: number) => height - (value / maxStack) * height;

  const seriesPolygons = series.map((entry, seriesIndex) => {
    const top = Array.from({ length: pointCount }, (_, idx) => {
      const x = pointCount > 1 ? idx * stepX : width / 2;
      const y = toY(cumulativeAt(idx, seriesIndex));
      return `${x},${Number.isFinite(y) ? y : height}`;
    });
    const bottom = Array.from({ length: pointCount }, (_, idx) => {
      const revIdx = pointCount - 1 - idx;
      const x = pointCount > 1 ? revIdx * stepX : width / 2;
      const y = toY(cumulativeBelow(revIdx, seriesIndex));
      return `${x},${Number.isFinite(y) ? y : height}`;
    });
    return {
      id: entry.id,
      color: entry.color,
      points: [...top, ...bottom].join(" "),
    };
  });

  const latestValues = series.reduce<Record<string, number>>((acc, entry) => {
    acc[entry.id] = Number(entry.values[pointCount - 1] ?? 0);
    return acc;
  }, {});

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-32 w-full cursor-crosshair"
        onClick={(event) => {
          if (!onPointClick) return;
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
          const idx = Math.round(ratio * Math.max(pointCount - 1, 0));
          const pointValues = series.reduce<Record<string, number>>((acc, entry) => {
            acc[entry.id] = Number(entry.values[idx] ?? 0);
            return acc;
          }, {});
          onPointClick(idx, labels[idx] ?? "", pointValues);
        }}
      >
        {seriesPolygons.map((polygon) => (
          <polygon key={polygon.id} points={polygon.points} fill={polygon.color} fillOpacity={0.35} />
        ))}
        {series.map((entry, seriesIndex) => {
          const points = Array.from({ length: pointCount }, (_, idx) => {
            const x = pointCount > 1 ? idx * stepX : width / 2;
            const y = toY(cumulativeAt(idx, seriesIndex));
            return `${x},${Number.isFinite(y) ? y : height}`;
          }).join(" ");
          return (
            <polyline
              key={`${entry.id}-line`}
              points={points}
              fill="none"
              stroke={entry.color}
              strokeWidth={1.8}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-3">
        {series.map((entry) => (
          <p key={entry.id} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-neutral-300">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
            <span>{entry.label}</span>
            <span className="tabular-nums text-slate-800 dark:text-neutral-100">
              {Math.round(latestValues[entry.id] ?? 0)}
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

export type { StackedAreaSeries };
