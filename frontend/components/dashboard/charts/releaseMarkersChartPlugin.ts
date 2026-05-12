"use client";

import type { Chart, Plugin } from "chart.js";

type ReleaseMarkerPluginOpts = { fractions: readonly number[] };

function readOpts(chart: Chart): ReleaseMarkerPluginOpts | undefined {
  const plugins = chart.options.plugins as Record<string, unknown> | undefined;
  const raw = plugins?.lumonoxReleaseMarkers;
  if (!raw || typeof raw !== "object") {
    return undefined;
  }
  const fr = (raw as { fractions?: unknown }).fractions;
  if (!Array.isArray(fr) || !fr.every((x) => typeof x === "number" && Number.isFinite(x))) {
    return undefined;
  }
  return { fractions: fr };
}

function xAtFractionalCategoryIndex(chart: Chart, frac: number): number | null {
  const meta = chart.getDatasetMeta(0);
  const pts = meta?.data;
  const n = pts?.length ?? 0;
  if (!pts || n < 1) {
    return null;
  }
  const clamped = Math.max(0, Math.min(frac, n - 1e-6));
  const i0 = Math.floor(clamped);
  const i1 = Math.min(n - 1, i0 + 1);
  const t = clamped - i0;
  const el0 = pts[i0] as { x?: number };
  const el1 = pts[i1] as { x?: number };
  const x0 = el0?.x;
  const x1 = el1?.x;
  if (typeof x0 !== "number" || !Number.isFinite(x0)) {
    return null;
  }
  if (i0 === i1 || typeof x1 !== "number" || !Number.isFinite(x1)) {
    return x0;
  }
  return x0 + t * (x1 - x0);
}

/** Vertical lines at fractional category indices (shared by bar + line charts). */
export const lumonoxReleaseMarkersVerticalLines: Plugin = {
  id: "lumonoxReleaseMarkersVerticalLines",
  afterDatasetsDraw(chart: Chart) {
    const opts = readOpts(chart);
    if (!opts?.fractions.length) {
      return;
    }
    const { ctx, chartArea } = chart;
    if (!chartArea) {
      return;
    }
    ctx.save();
    ctx.strokeStyle = "rgba(79, 70, 229, 0.55)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    for (const frac of opts.fractions) {
      const x = xAtFractionalCategoryIndex(chart, frac);
      if (x === null) {
        continue;
      }
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
  },
};
