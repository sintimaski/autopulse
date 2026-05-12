"use client";

/**
 * Tree-shaken Chart.js registration (see https://www.chartjs.org/docs/latest/getting-started/integration.html).
 * Import this module once before rendering any chart (e.g. via `chartCanvas.tsx`).
 */
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  DoughnutController,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  ScatterController,
  Tooltip,
  type ActiveDataPoint,
  type Chart,
  type Plugin,
} from "chart.js";

import { lumonoxReleaseMarkersVerticalLines } from "./releaseMarkersChartPlugin";

type ChartWithTooltipPreserve = Chart & {
  __apTooltipPreserve?: ActiveDataPoint[];
  __apTooltipCaret?: { x: number; y: number };
};

/** Keeps hover tooltip active across `chart.update()` when live data refreshes (no re-hover). */
const lumonoxTooltipPersistAcrossUpdate: Plugin = {
  id: "lumonoxTooltipPersistAcrossUpdate",
  beforeUpdate(chart) {
    const c = chart as ChartWithTooltipPreserve;
    const fromChart = chart.getActiveElements();
    const tooltip = chart.tooltip;
    const fromTooltip = tooltip?.getActiveElements?.() ?? [];
    const source = fromChart.length ? fromChart : fromTooltip;
    if (!source.length) {
      c.__apTooltipPreserve = undefined;
      c.__apTooltipCaret = undefined;
      return;
    }
    c.__apTooltipPreserve = source.map((e) => ({
      datasetIndex: e.datasetIndex,
      index: e.index,
    }));
    c.__apTooltipCaret =
      tooltip && tooltip.opacity > 0 ? { x: tooltip.caretX, y: tooltip.caretY } : undefined;
  },
  afterUpdate(chart) {
    const c = chart as ChartWithTooltipPreserve;
    const saved = c.__apTooltipPreserve;
    const caret = c.__apTooltipCaret;
    c.__apTooltipPreserve = undefined;
    c.__apTooltipCaret = undefined;
    if (!saved?.length) {
      return;
    }
    const first = saved[0];
    const meta = chart.getDatasetMeta(first.datasetIndex);
    const element = meta?.data?.[first.index];
    if (!element) {
      return;
    }
    chart.setActiveElements(saved);
    const el = element as unknown as { getCenterPoint?: () => { x: number; y: number } };
    const pos =
      typeof el.getCenterPoint === "function"
        ? el.getCenterPoint()
        : caret ?? { x: chart.chartArea?.left ?? 0, y: chart.chartArea?.top ?? 0 };
    chart.tooltip?.setActiveElements(saved, pos);
  },
};

ChartJS.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  ScatterController,
  Tooltip,
  lumonoxTooltipPersistAcrossUpdate,
  lumonoxReleaseMarkersVerticalLines,
);
