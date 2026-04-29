"use client";

type HeatmapCell = {
  x: string;
  y: string;
  value: number;
};

export function HeatmapGrid({
  cells,
  xLabels,
  yLabels,
  onCellClick,
}: {
  cells: HeatmapCell[];
  xLabels: string[];
  yLabels: string[];
  onCellClick?: (cell: HeatmapCell) => void;
}) {
  if (!cells.length || !xLabels.length || !yLabels.length) {
    return <p className="text-sm text-slate-500 dark:text-neutral-400">No heatmap data available.</p>;
  }
  const lookup = new Map(cells.map((cell) => [`${cell.x}|${cell.y}`, cell.value] as const));
  let max = 1;
  for (const cell of cells) {
    if (cell.value > max) {
      max = cell.value;
    }
  }
  const tone = (value: number) => {
    const ratio = value / max;
    if (ratio >= 0.75) return "bg-rose-500/80 text-white";
    if (ratio >= 0.5) return "bg-rose-400/70 text-rose-950";
    if (ratio >= 0.25) return "bg-amber-400/70 text-amber-950";
    if (ratio > 0) return "bg-slate-300/80 text-slate-900 dark:bg-neutral-700 dark:text-neutral-100";
    return "bg-slate-100 text-slate-500 dark:bg-neutral-900 dark:text-neutral-500";
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th className="w-20 text-left text-slate-500 dark:text-neutral-400">Route</th>
            {xLabels.map((xLabel) => (
              <th key={xLabel} className="px-2 text-center text-slate-500 dark:text-neutral-400">
                {xLabel}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {yLabels.map((yLabel) => (
            <tr key={yLabel}>
              <th className="max-w-[180px] truncate text-left font-normal text-slate-600 dark:text-neutral-300">
                {yLabel}
              </th>
              {xLabels.map((xLabel) => {
                const value = lookup.get(`${xLabel}|${yLabel}`) ?? 0;
                const cell = { x: xLabel, y: yLabel, value };
                return (
                  <td key={`${xLabel}-${yLabel}`} className="px-1">
                    <div
                      title={`${yLabel} · ${xLabel}: ${value}`}
                      onClick={onCellClick ? () => onCellClick(cell) : undefined}
                      className={`rounded px-2 py-1 text-center tabular-nums ${tone(value)} ${onCellClick ? "cursor-pointer" : ""}`}
                    >
                      {value}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export type { HeatmapCell };
