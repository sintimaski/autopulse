"use client";

import { useMemo } from "react";

import {
  useDashboardAlertsDataSlice,
  useDashboardDiagnosisDataSlice,
  useDashboardHomeDataSlice,
  useDashboardLogsDataSlice,
} from "../DashboardDataContext";

export function useDashboardHomeSlice() {
  const d = useDashboardHomeDataSlice();
  return useMemo(
    () => ({
      overview: d.overview,
      overviewExtended: d.overviewExtended,
      dashboardWidgets: d.dashboardWidgets,
      requests: d.requests,
      errorGroups: d.errorGroups,
      sparklineSeries: d.sparklineSeries,
      operationalSignals: d.operationalSignals,
      rawItems: d.rawItems,
      windowMinutes: d.windowMinutes,
      isAbsoluteWindow: d.isAbsoluteWindow,
      windowFromTimestamp: d.windowFromTimestamp,
      windowToTimestamp: d.windowToTimestamp,
      method: d.method,
      statusClass: d.statusClass,
      requestLimit: d.requestLimit,
      errorGroupLimit: d.errorGroupLimit,
      errorGroupSort: d.errorGroupSort,
      minLatencyMs: d.minLatencyMs,
      maxLatencyMs: d.maxLatencyMs,
      pathQuery: d.pathQuery,
      serverEnvironmentQuery: d.serverEnvironmentQuery,
      serverServiceQuery: d.serverServiceQuery,
      sqlFilterApplied: d.sqlFilterApplied,
      sqlFilterEnabled: d.sqlFilterEnabled,
      errorMessage: d.errorMessage,
    }),
    [
      d.overview,
      d.overviewExtended,
      d.dashboardWidgets,
      d.requests,
      d.errorGroups,
      d.sparklineSeries,
      d.operationalSignals,
      d.rawItems,
      d.windowMinutes,
      d.isAbsoluteWindow,
      d.windowFromTimestamp,
      d.windowToTimestamp,
      d.method,
      d.statusClass,
      d.requestLimit,
      d.errorGroupLimit,
      d.errorGroupSort,
      d.minLatencyMs,
      d.maxLatencyMs,
      d.pathQuery,
      d.serverEnvironmentQuery,
      d.serverServiceQuery,
      d.sqlFilterApplied,
      d.sqlFilterEnabled,
      d.errorMessage,
    ],
  );
}

export function useDashboardDiagnosisSlice() {
  const d = useDashboardDiagnosisDataSlice();
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
  const d = useDashboardAlertsDataSlice();
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
  const d = useDashboardLogsDataSlice();
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
