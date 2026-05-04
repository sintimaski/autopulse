"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { DashboardChartShowcaseGrid } from "./DashboardChartShowcaseGrid";
import { DashboardCustomWidgetCharts } from "./DashboardCustomWidgetCharts";
import {
  buildShowroomChartShowcaseMock,
  buildWidgetsShowroomMockPoints,
  getWidgetsShowroomMockDefinitions,
} from "./widgetsShowroomMockData";

const REFRESH_MS = 2000;

export function WidgetsShowroomContent() {
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
    <section className="space-y-8">
      <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h1 className="text-lg font-semibold text-slate-900 dark:text-neutral-50">Widget showroom</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
          Frontend-only mock metrics on a {REFRESH_MS / 1000}s cadence: the same SDK widget types and the same six chart
          panels as the backend widget gallery, without ingest or live overview data. Values drift with smooth noise, like a
          live stream.
        </p>
        <p className="mt-3 text-sm text-slate-600 dark:text-neutral-400">
          <Link
            href="/widgets-showcase"
            className="font-medium text-sky-600 underline decoration-sky-600/30 underline-offset-2 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300"
          >
            Widget gallery
          </Link>{" "}
          uses your project&apos;s real overview scope and optional SDK widget payloads.
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
        title="Mock chart options showcase"
        description="Same layout as the backend gallery: line, bar, donut, histogram, scatter, and stacked area — driven here by synthetic series."
      />
    </section>
  );
}
