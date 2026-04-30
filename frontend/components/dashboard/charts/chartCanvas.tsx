"use client";

import "./chartJsRegister";

import dynamic from "next/dynamic";

function ChartLoading() {
  return <div className="h-full min-h-[4rem] w-full animate-pulse rounded-md bg-slate-200/40 dark:bg-neutral-700/40" />;
}

export const CanvasLine = dynamic(() => import("react-chartjs-2").then((m) => m.Line), {
  ssr: false,
  loading: ChartLoading,
});

export const CanvasBar = dynamic(() => import("react-chartjs-2").then((m) => m.Bar), {
  ssr: false,
  loading: ChartLoading,
});

export const CanvasDoughnut = dynamic(() => import("react-chartjs-2").then((m) => m.Doughnut), {
  ssr: false,
  loading: ChartLoading,
});

export const CanvasScatter = dynamic(() => import("react-chartjs-2").then((m) => m.Scatter), {
  ssr: false,
  loading: ChartLoading,
});
