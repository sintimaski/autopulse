"use client";

import type {
  AlertDispatchesResponse,
  DiagnosisFailureRoutesResponse,
  DiagnosisTimelineResponse,
  RecentJobFailuresResponse,
  ErrorGroupsResponse,
  OverviewExtendedResponse,
  OverviewResponse,
  RequestsResponse,
} from "./dashboardTypes";

const STORAGE_KEY = "autopulse.dashboard.data.v1";
const SNAPSHOT_TTL_MS = 20_000;
const inMemorySnapshots = new Map<string, DashboardSnapshotRecord>();

export type DashboardSnapshotPayload = {
  overview: OverviewResponse;
  overviewExtended?: OverviewExtendedResponse;
  requests: RequestsResponse;
  errorGroups?: ErrorGroupsResponse;
  /** Omitted on newer home snapshots (diagnosis is fetched only on `/diagnosis`). */
  diagnosisTimeline?: DiagnosisTimelineResponse;
  diagnosisFailures?: DiagnosisFailureRoutesResponse;
  recentJobFailures?: RecentJobFailuresResponse;
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
  const memoryRecord = inMemorySnapshots.get(scopeKey);
  if (memoryRecord) {
    const ageMs = Date.now() - Date.parse(memoryRecord.savedAt);
    if (Number.isFinite(ageMs) && ageMs <= SNAPSHOT_TTL_MS) {
      return memoryRecord.payload;
    }
    inMemorySnapshots.delete(scopeKey);
  }
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
    const ageMs = Date.now() - Date.parse(parsed.savedAt);
    if (!Number.isFinite(ageMs) || ageMs > SNAPSHOT_TTL_MS) {
      return null;
    }
    if (
      !parsed.payload?.overview ||
      !parsed.payload?.requests
    ) {
      return null;
    }
    inMemorySnapshots.set(scopeKey, parsed);
    return parsed.payload;
  } catch {
    return null;
  }
}

export function writeDashboardSnapshot(scopeKey: string, payload: DashboardSnapshotPayload): void {
  const record: DashboardSnapshotRecord = {
    scopeKey,
    savedAt: new Date().toISOString(),
    payload,
  };
  inMemorySnapshots.set(scopeKey, record);
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    // Quota or private mode — ignore.
  }
}
