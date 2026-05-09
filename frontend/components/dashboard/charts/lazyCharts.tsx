"use client";

import dynamic from "next/dynamic";

import { CardSpinner } from "../../ui/CardSpinner";

export { ChartPanel } from "./ChartPanel";
export type { HistogramBucket } from "./HistogramChart";
export type { MultiSeriesLineChartSeries } from "./MultiSeriesLineChart";
export type { ScatterPlotPoint } from "./ScatterPlotChart";
export type { StackedAreaSeries } from "./StackedAreaChart";

function ChartSkeleton() {
  return <CardSpinner size="embed" label="Loading chart…" className="h-40 min-h-[10rem]" />;
}

export const BreakdownBarChart = dynamic(
  () => import("./BreakdownBarChart").then((m) => m.BreakdownBarChart),
  { loading: ChartSkeleton },
);

export const DonutChart = dynamic(
  () => import("./DonutChart").then((m) => m.DonutChart),
  { loading: ChartSkeleton },
);

export const HeatmapGrid = dynamic(
  () => import("./HeatmapGrid").then((m) => m.HeatmapGrid),
  { loading: ChartSkeleton },
);

export const HistogramChart = dynamic(
  () => import("./HistogramChart").then((m) => m.HistogramChart),
  { loading: ChartSkeleton },
);

export const MultiSeriesLineChart = dynamic(
  () => import("./MultiSeriesLineChart").then((m) => m.MultiSeriesLineChart),
  { loading: ChartSkeleton },
);

export const PercentileLadder = dynamic(
  () => import("./PercentileLadder").then((m) => m.PercentileLadder),
  { loading: ChartSkeleton },
);

export const ScatterPlotChart = dynamic(
  () => import("./ScatterPlotChart").then((m) => m.ScatterPlotChart),
  { loading: ChartSkeleton },
);

export const StackedAreaChart = dynamic(
  () => import("./StackedAreaChart").then((m) => m.StackedAreaChart),
  { loading: ChartSkeleton },
);

export const TimeSeriesLineChart = dynamic(
  () => import("./TimeSeriesLineChart").then((m) => m.TimeSeriesLineChart),
  { loading: ChartSkeleton },
);
