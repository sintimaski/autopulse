"use client";

import { useMemo } from "react";

import { normalizeSchedulerJobs, normalizeSystemDiagnostics } from "../../../utils/systemDiagnostics";
import type { DashboardSystemDiagnosticsResponse } from "../dashboardTypes";

export function useSettingsSystemDiagnosticsDerived(snapshot: DashboardSystemDiagnosticsResponse | null) {
  const systemDiagnosticsSummary = useMemo(
    () => normalizeSystemDiagnostics(snapshot),
    [snapshot],
  );
  const schedulerJobs = useMemo(() => normalizeSchedulerJobs(snapshot), [snapshot]);
  return { systemDiagnosticsSummary, schedulerJobs };
}
