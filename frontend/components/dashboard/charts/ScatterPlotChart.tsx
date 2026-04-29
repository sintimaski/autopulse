"use client";

type ScatterPlotPoint = {
  id: string;
  x: number;
  y: number;
  label: string;
  tone?: "neutral" | "warning" | "danger";
};

type ScatterPlotChartProps = {
  points: ScatterPlotPoint[];
  xLabel: string;
  yLabel: string;
  emptyMessage?: string;
  onPointClick?: (point: ScatterPlotPoint) => void;
};

export function ScatterPlotChart({
  points,
  xLabel,
  yLabel,
  emptyMessage = "No scatter data in this range.",
  onPointClick,
}: ScatterPlotChartProps) {
  const width = 520;
  const height = 170;
  if (!points.length) {
    return <p className="text-sm text-slate-600 dark:text-neutral-300">{emptyMessage}</p>;
  }

  const maxX = Math.max(...points.map((point) => Math.max(0, point.x)), 1);
  const maxY = Math.max(...points.map((point) => Math.max(0, point.y)), 1);
  const toneColor = (tone: ScatterPlotPoint["tone"]) => {
    if (tone === "danger") return "#f43f5e";
    if (tone === "warning") return "#f59e0b";
    return "#38bdf8";
  };

  return (
    <div className="space-y-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full">
        <line x1={0} y1={height - 1} x2={width} y2={height - 1} stroke="#64748b" strokeOpacity={0.3} />
        <line x1={1} y1={0} x2={1} y2={height} stroke="#64748b" strokeOpacity={0.3} />
        {points.map((point) => {
          const x = (Math.max(0, point.x) / maxX) * width;
          const y = height - (Math.max(0, point.y) / maxY) * height;
          return (
            <circle
              key={point.id}
              cx={x}
              cy={Number.isFinite(y) ? y : height}
              r={4.2}
              fill={toneColor(point.tone)}
              fillOpacity={0.85}
              stroke="#ffffff"
              strokeWidth={1}
              className={onPointClick ? "cursor-pointer" : ""}
              onClick={() => onPointClick?.(point)}
            >
              <title>{point.label}</title>
            </circle>
          );
        })}
      </svg>
      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-neutral-400">
        <span>{yLabel}</span>
        <span>{xLabel}</span>
      </div>
    </div>
  );
}

export type { ScatterPlotPoint };
