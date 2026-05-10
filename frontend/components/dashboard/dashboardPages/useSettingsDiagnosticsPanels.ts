"use client";

import { useEffect, useMemo, useState } from "react";

import { normalizeSchedulerJobs, normalizeSystemDiagnostics } from "../../../utils/systemDiagnostics";

import { dashboardSessionFetch } from "../dashboardSessionFetch";
import type { DashboardSystemDiagnosticsResponse } from "../dashboardTypes";
import {
  parseDashboardInternalMetricsResponse,
  parseDashboardSystemDiagnosticsResponse,
  parseEventPlaneCutoverSettings,
} from "../../../utils/dashboardResponseGuards";

import type { InternalMetricsSnapshot } from "./settingsContentTypes";

export function settingsMetricStatusClass(ok: boolean | null): string {
  if (ok === true) {
    return "border-emerald-300 bg-emerald-50/90 dark:border-emerald-900/70 dark:bg-emerald-950/35";
  }
  if (ok === false) {
    return "border-rose-300 bg-rose-50/90 dark:border-rose-900/70 dark:bg-rose-950/35";
  }
  return "border-slate-200 bg-slate-50/70 dark:border-neutral-700 dark:bg-neutral-800/60";
}

type UseSettingsDiagnosticsPanelsArgs = {
  canViewInternalMetrics: boolean;
  canViewSystemDiagnostics: boolean;
  canManageEventPlaneCutover: boolean;
};

export function useSettingsDiagnosticsPanels({
  canViewInternalMetrics,
  canViewSystemDiagnostics,
  canManageEventPlaneCutover,
}: UseSettingsDiagnosticsPanelsArgs) {
  const [internalMetricsLoadState, setInternalMetricsLoadState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [internalMetricsEnabled, setInternalMetricsEnabled] = useState(false);
  const [internalMetricsReason, setInternalMetricsReason] = useState<string | null>(null);
  const [internalMetricsSnapshot, setInternalMetricsSnapshot] = useState<InternalMetricsSnapshot | null>(null);

  const [systemDiagnosticsLoadState, setSystemDiagnosticsLoadState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [systemDiagnosticsSnapshot, setSystemDiagnosticsSnapshot] =
    useState<DashboardSystemDiagnosticsResponse | null>(null);
  const [systemDiagnosticsMessage, setSystemDiagnosticsMessage] = useState<string | null>(null);

  const [eventPlaneCutoverLoadState, setEventPlaneCutoverLoadState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [eventPlaneUseSnapshotRead, setEventPlaneUseSnapshotRead] = useState(false);
  const [eventPlaneCutoverMessage, setEventPlaneCutoverMessage] = useState<string | null>(null);

  const systemDiagnosticsSummary = useMemo(
    () => normalizeSystemDiagnostics(systemDiagnosticsSnapshot),
    [systemDiagnosticsSnapshot],
  );
  const schedulerJobs = useMemo(
    () => normalizeSchedulerJobs(systemDiagnosticsSnapshot),
    [systemDiagnosticsSnapshot],
  );

  useEffect(() => {
    let cancelled = false;
    if (!canViewInternalMetrics) {
      queueMicrotask(() => {
        if (cancelled) {
          return;
        }
        setInternalMetricsLoadState("idle");
        setInternalMetricsEnabled(false);
        setInternalMetricsReason(null);
        setInternalMetricsSnapshot(null);
      });
      return;
    }
    queueMicrotask(() => {
      if (cancelled) {
        return;
      }
      setInternalMetricsLoadState("loading");
    });
    void (async () => {
      try {
        const response = await dashboardSessionFetch("/dashboard/internal-metrics");
        if (!response.ok) {
          throw new Error(`internal-metrics failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const payload = parseDashboardInternalMetricsResponse(raw);
        if (cancelled) {
          return;
        }
        if (!payload) {
          throw new Error("internal-metrics returned unexpected JSON shape");
        }
        const metrics =
          payload.metrics && typeof payload.metrics === "object"
            ? (payload.metrics as InternalMetricsSnapshot)
            : null;
        setInternalMetricsEnabled(Boolean(payload.enabled));
        setInternalMetricsReason(payload.reason ?? null);
        setInternalMetricsSnapshot(metrics);
        setInternalMetricsLoadState("ready");
      } catch {
        if (!cancelled) {
          setInternalMetricsLoadState("error");
          setInternalMetricsEnabled(false);
          setInternalMetricsReason("Could not load internal metrics from the server.");
          setInternalMetricsSnapshot(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canViewInternalMetrics]);

  useEffect(() => {
    let cancelled = false;
    if (!canViewSystemDiagnostics) {
      queueMicrotask(() => {
        if (cancelled) {
          return;
        }
        setSystemDiagnosticsLoadState("idle");
        setSystemDiagnosticsSnapshot(null);
      });
      return;
    }
    queueMicrotask(() => {
      if (!cancelled) {
        setSystemDiagnosticsLoadState("loading");
      }
    });
    void (async () => {
      try {
        const response = await dashboardSessionFetch("/dashboard/system-diagnostics");
        if (!response.ok) {
          throw new Error(`system-diagnostics failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const payload = parseDashboardSystemDiagnosticsResponse(raw);
        if (cancelled) {
          return;
        }
        if (!payload) {
          throw new Error("system-diagnostics returned unexpected JSON shape");
        }
        setSystemDiagnosticsSnapshot(payload);
        setSystemDiagnosticsLoadState("ready");
      } catch {
        if (!cancelled) {
          setSystemDiagnosticsLoadState("error");
          setSystemDiagnosticsSnapshot(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canViewSystemDiagnostics]);

  useEffect(() => {
    let cancelled = false;
    if (!canManageEventPlaneCutover) {
      queueMicrotask(() => {
        if (cancelled) {
          return;
        }
        setEventPlaneCutoverLoadState("idle");
        setEventPlaneUseSnapshotRead(false);
      });
      return;
    }
    queueMicrotask(() => {
      if (!cancelled) {
        setEventPlaneCutoverLoadState("loading");
      }
    });
    void (async () => {
      try {
        const response = await dashboardSessionFetch("/dashboard/event-plane-cutover");
        if (!response.ok) {
          throw new Error(`event-plane-cutover failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const payload = parseEventPlaneCutoverSettings(raw);
        if (cancelled) {
          return;
        }
        if (!payload) {
          throw new Error("event-plane-cutover returned unexpected JSON shape");
        }
        setEventPlaneUseSnapshotRead(Boolean(payload.use_snapshot_read));
        setEventPlaneCutoverLoadState("ready");
      } catch {
        if (!cancelled) {
          setEventPlaneCutoverLoadState("error");
          setEventPlaneCutoverMessage("Could not load Event Plane cutover setting.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canManageEventPlaneCutover]);

  return {
    internalMetricsLoadState,
    internalMetricsEnabled,
    internalMetricsReason,
    internalMetricsSnapshot,
    systemDiagnosticsLoadState,
    systemDiagnosticsSnapshot,
    systemDiagnosticsSummary,
    schedulerJobs,
    systemDiagnosticsMessage,
    setSystemDiagnosticsMessage,
    eventPlaneCutoverLoadState,
    eventPlaneUseSnapshotRead,
    setEventPlaneUseSnapshotRead,
    eventPlaneCutoverMessage,
    setEventPlaneCutoverMessage,
  };
}
