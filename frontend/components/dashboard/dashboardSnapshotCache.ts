"use client";

import type {
  AlertDispatchesResponse,
  DiagnosisFailureRoutesResponse,
  DiagnosisTimelineResponse,
  ErrorGroupsResponse,
  OverviewExtendedResponse,
  OverviewResponse,
  RequestsResponse,
} from "./dashboardTypes";

const STORAGE_KEY = "autopulse.dashboard.data.v1";

export type DashboardSnapshotPayload = {
  overview: OverviewResponse;
  overviewExtended: OverviewExtendedResponse;
  requests: RequestsResponse;
  errorGroups: ErrorGroupsResponse;
  /** Omitted on newer home snapshots (diagnosis is fetched only on `/diagnosis`). */
  diagnosisTimeline?: DiagnosisTimelineResponse;
  diagnosisFailures?: DiagnosisFailureRoutesResponse;
  alertDispatches?: AlertDispatchesResponse;
};

export type DashboardSnapshotRecord = {
  scopeKey: string;
  savedAt: string;
  payload: DashboardSnapshotPayload;
};

export function buildDashboardDataCacheScopeKey(parts: {
  windowFrom: string;
  windowTo: string;
  windowMinutes: number;
  isAbsoluteWindow: boolean;
  method: string;
  statusClass: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  pathQuery: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  requestLimit: number;
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
  errorGroupSort: string;
  sqlFilterEnabled: boolean;
  sqlFilterApplied: string;
}): string {
  return JSON.stringify(parts);
}

export function readDashboardSnapshot(scopeKey: string): DashboardSnapshotPayload | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as DashboardSnapshotRecord;
    if (!parsed || typeof parsed.scopeKey !== "string" || parsed.scopeKey !== scopeKey) {
      return null;
    }
    if (
      !parsed.payload?.overview ||
      !parsed.payload?.overviewExtended ||
      !parsed.payload?.requests ||
      !parsed.payload?.errorGroups
    ) {
      return null;
    }
    return parsed.payload;
  } catch {
    return null;
  }
}

export function writeDashboardSnapshot(scopeKey: string, payload: DashboardSnapshotPayload): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const record: DashboardSnapshotRecord = {
      scopeKey,
      savedAt: new Date().toISOString(),
      payload,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    // Quota or private mode — ignore.
  }
}
