"use client";

import "./chartJsRegister";

import dynamic from "next/dynamic";

import { CardSpinner } from "../../ui/CardSpinner";

function ChartLoading() {
  return <CardSpinner size="embed" label="Loading chart…" className="h-full min-h-[4rem]" />;
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
