"use client";

import { useEffect, type MutableRefObject } from "react";

import { DASHBOARD_REFRESH_INTERVAL_MS } from "../dashboardDataFetchUtils";

/**
 * Poll dashboard data on a fixed cadence.
 */
export function useDashboardPollingRefresh(options: {
  hasSession: boolean;
  liveRefreshPausedRef: MutableRefObject<boolean>;
  dashboardFetchInFlightRef: MutableRefObject<boolean>;
  dashboardQueuedRefreshRef: MutableRefObject<boolean>;
  bumpRefresh: () => void;
  pollingTimerRef: MutableRefObject<ReturnType<typeof setInterval> | null>;
}): void {
  const {
    hasSession,
    liveRefreshPausedRef,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    bumpRefresh,
    pollingTimerRef,
  } = options;

  useEffect(
    () => {
      if (!hasSession) {
        if (pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current);
          pollingTimerRef.current = null;
        }
        return;
      }
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
      }
      pollingTimerRef.current = setInterval(() => {
        if (liveRefreshPausedRef.current) {
          return;
        }
        if (typeof document !== "undefined" && document.visibilityState !== "visible") {
          return;
        }
        if (dashboardFetchInFlightRef.current) {
          dashboardQueuedRefreshRef.current = true;
        } else {
          bumpRefresh();
        }
      }, DASHBOARD_REFRESH_INTERVAL_MS);
      return () => {
        if (pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current);
          pollingTimerRef.current = null;
        }
      };
    },
    // Refs read via `.current` inside the effect (stable ref objects); match prior provider deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hasSession, bumpRefresh],
  );
}

/** When the tab becomes visible, bump dashboard refresh (coalesced with in-flight fetch). */
export function useDashboardVisibilityRefreshBump(options: {
  hasSession: boolean;
  liveRefreshPausedRef: MutableRefObject<boolean>;
  dashboardFetchInFlightRef: MutableRefObject<boolean>;
  dashboardQueuedRefreshRef: MutableRefObject<boolean>;
  bumpRefresh: () => void;
}): void {
  const { hasSession, liveRefreshPausedRef, dashboardFetchInFlightRef, dashboardQueuedRefreshRef, bumpRefresh } =
    options;

  useEffect(
    () => {
      if (!hasSession) {
        return;
      }
      const onVisibilityChange = () => {
        if (liveRefreshPausedRef.current) {
          return;
        }
        if (typeof document === "undefined" || document.visibilityState !== "visible") {
          return;
        }
        if (dashboardFetchInFlightRef.current) {
          dashboardQueuedRefreshRef.current = true;
          return;
        }
        bumpRefresh();
      };
      document.addEventListener("visibilitychange", onVisibilityChange);
      return () => {
        document.removeEventListener("visibilitychange", onVisibilityChange);
      };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hasSession, bumpRefresh],
  );
}
