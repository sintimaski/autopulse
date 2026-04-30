"use client";

import { useMemo } from "react";

import { useDashboardData } from "../DashboardDataContext";

export function useDashboardHomeSlice() {
  const d = useDashboardData();
  return useMemo(
    () => ({
      overview: d.overview,
      overviewExtended: d.overviewExtended,
      dashboardWidgets: d.dashboardWidgets,
      requests: d.requests,
      errorGroups: d.errorGroups,
      sparklineSeries: d.sparklineSeries,
      operationalSignals: d.operationalSignals,
    }),
    [
      d.overview,
      d.overviewExtended,
      d.dashboardWidgets,
      d.requests,
      d.errorGroups,
      d.sparklineSeries,
      d.operationalSignals,
    ],
  );
}

export function useDashboardDiagnosisSlice() {
  const d = useDashboardData();
  return useMemo(
    () => ({
      diagnosisTimeline: d.diagnosisTimeline,
      diagnosisFailures: d.diagnosisFailures,
      diagnosisErrorGroupEvents: d.diagnosisErrorGroupEvents,
      errorGroups: d.errorGroups,
    }),
    [d.diagnosisTimeline, d.diagnosisFailures, d.diagnosisErrorGroupEvents, d.errorGroups],
  );
}

export function useDashboardAlertsSlice() {
  const d = useDashboardData();
  return useMemo(
    () => ({
      alertDispatches: d.alertDispatches,
      alertSettings: d.alertSettings,
      alertCapabilities: d.alertCapabilities,
    }),
    [d.alertDispatches, d.alertSettings, d.alertCapabilities],
  );
}

export function useDashboardLogsSlice() {
  const d = useDashboardData();
  return useMemo(
    () => ({
      requests: d.requests,
      filteredSorted: d.filteredSorted,
      grouped: d.grouped,
      availableServices: d.availableServices,
      availableEnvironments: d.availableEnvironments,
    }),
    [d.requests, d.filteredSorted, d.grouped, d.availableServices, d.availableEnvironments],
  );
}
