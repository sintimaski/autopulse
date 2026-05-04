"use client";

import {
  BreakdownBarChart,
  ChartPanel,
  DonutChart,
  HistogramChart,
  ScatterPlotChart,
  StackedAreaChart,
  TimeSeriesLineChart,
  type ScatterPlotPoint,
  type StackedAreaSeries,
} from "../charts";

export type DashboardChartShowcaseGridProps = {
  lineLabels: string[];
  lineValues: number[];
  barItems: { key: string; value: number }[];
  donutItems: { id: string; label: string; value: number; color: string }[];
  donutCenterValue: string;
  histogramBuckets: { label: string; count: number }[];
  scatterPoints: ScatterPlotPoint[];
  stackedLabels: string[];
  stackedSeries: StackedAreaSeries[];
  title?: string;
  description?: string;
};

/**
 * Six chart panels matching the backend widget gallery “Chart options showcase” (line, bar, donut, histogram, scatter, stacked area).
 */
export function DashboardChartShowcaseGrid({
  lineLabels,
  lineValues,
  barItems,
  donutItems,
  donutCenterValue,
  histogramBuckets,
  scatterPoints,
  stackedLabels,
  stackedSeries,
  title = "Chart options showcase",
  description = "All available chart styles shown together: line, bars, donut, histogram, scatter, and stacked area.",
}: DashboardChartShowcaseGridProps) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">{title}</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">{description}</p>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <ChartPanel title="Line chart">
          <TimeSeriesLineChart
            title="Error trend"
            labels={lineLabels}
            values={lineValues}
            color="#f43f5e"
            formatValue={(value) => value.toFixed(0)}
          />
        </ChartPanel>
        <ChartPanel title="Bar chart">
          <BreakdownBarChart items={barItems} valueLabel="req" />
        </ChartPanel>
        <ChartPanel title="Donut chart">
          <DonutChart
            title="Status classes"
            items={donutItems}
            centerLabel="Total"
            centerValue={donutCenterValue}
          />
        </ChartPanel>
        <ChartPanel title="Histogram">
          <HistogramChart buckets={histogramBuckets} />
        </ChartPanel>
        <ChartPanel title="Scatter plot">
          <ScatterPlotChart points={scatterPoints} xLabel="Request volume" yLabel="Error rate %" />
        </ChartPanel>
        <ChartPanel title="Stacked area">
          <StackedAreaChart labels={stackedLabels} series={stackedSeries} />
        </ChartPanel>
      </div>
    </section>
  );
}
