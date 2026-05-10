"use client";

import {
  useDashboardAlertsDataSlice,
  useDashboardDiagnosisDataSlice,
  useDashboardHomeDataSlice,
  useDashboardLogsDataSlice,
} from "../DashboardDataContext";

/**
 * Thin selectors over slice contexts. Values are already memoized in
 * `DashboardDataProvider`; avoid a second `useMemo` layer (same deps, no extra stability).
 */
export function useDashboardHomeSlice() {
  return useDashboardHomeDataSlice();
}

export function useDashboardDiagnosisSlice() {
  return useDashboardDiagnosisDataSlice();
}

export function useDashboardAlertsSlice() {
  return useDashboardAlertsDataSlice();
}

export function useDashboardLogsSlice() {
  return useDashboardLogsDataSlice();
}
