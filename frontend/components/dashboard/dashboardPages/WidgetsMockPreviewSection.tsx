"use client";

import { useEffect, useMemo, useState } from "react";

import { DashboardChartShowcaseGrid } from "./DashboardChartShowcaseGrid";
import { DashboardCustomWidgetCharts } from "./DashboardCustomWidgetCharts";
import {
  buildShowroomChartShowcaseMock,
  buildWidgetsShowroomMockPoints,
  getWidgetsShowroomMockDefinitions,
} from "./widgetsShowroomMockData";

const REFRESH_MS = 2000;

/**
 * Timer-driven mock widgets + chart grid — same layouts as live gallery, no backend traffic required.
 */
export function WidgetsMockPreviewSection() {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setTick((value) => value + 1);
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);

  const definitions = useMemo(() => getWidgetsShowroomMockDefinitions(), []);
  const points = useMemo(() => buildWidgetsShowroomMockPoints(tick), [tick]);
  const chartShowcase = useMemo(() => buildShowroomChartShowcaseMock(tick), [tick]);

  return (
    <div className="space-y-8 border-t border-slate-200/80 pt-8 dark:border-neutral-800">
      <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-neutral-50">Mock preview</h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
          Synthetic metrics on a {REFRESH_MS / 1000}s cadence: the same SDK widget types and six chart panels as above,
          without ingest. Use this to validate layouts when the project has little or no traffic.
        </p>
      </div>

      <DashboardCustomWidgetCharts
        definitions={definitions}
        points={points}
        heading="Mock SDK widgets"
        description="All supported widget types fed from in-browser synthetic data."
        emptyMessage="No mock definitions (unexpected)."
      />

      <DashboardChartShowcaseGrid
        lineLabels={chartShowcase.lineLabels}
        lineValues={chartShowcase.lineValues}
        barItems={chartShowcase.barItems}
        donutItems={chartShowcase.donutItems}
        donutCenterValue={chartShowcase.donutCenterValue}
        histogramBuckets={chartShowcase.histogramBuckets}
        scatterPoints={chartShowcase.scatterPoints}
        stackedLabels={chartShowcase.stackedLabels}
        stackedSeries={chartShowcase.stackedSeries}
        title="Mock chart showcase"
        description="Line, bar, donut, histogram, scatter, and stacked area — same grid as the live section, driven by synthetic series."
      />
    </div>
  );
}
