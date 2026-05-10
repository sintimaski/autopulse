"use client";

import { useEffect, type MutableRefObject } from "react";

import { DASHBOARD_REFRESH_INTERVAL_MS } from "../dashboardDataFetchUtils";

/**
 * Fallback polling when the dashboard WebSocket is disconnected (keeps charts fresh without WS).
 * Lifted from `DashboardDataProvider` to shrink the main context module.
 */
export function useDashboardWsDisconnectedFallbackPoll(options: {
  hasSession: boolean;
  liveUpdatesConnected: boolean;
  liveRefreshPausedRef: MutableRefObject<boolean>;
  dashboardFetchInFlightRef: MutableRefObject<boolean>;
  dashboardQueuedRefreshRef: MutableRefObject<boolean>;
  bumpRefresh: () => void;
  liveFallbackRefreshTimerRef: MutableRefObject<ReturnType<typeof setInterval> | null>;
}): void {
  const {
    hasSession,
    liveUpdatesConnected,
    liveRefreshPausedRef,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    bumpRefresh,
    liveFallbackRefreshTimerRef,
  } = options;

  useEffect(
    () => {
      if (!hasSession || liveUpdatesConnected) {
        if (liveFallbackRefreshTimerRef.current) {
          clearInterval(liveFallbackRefreshTimerRef.current);
          liveFallbackRefreshTimerRef.current = null;
        }
        return;
      }
      if (liveFallbackRefreshTimerRef.current) {
        clearInterval(liveFallbackRefreshTimerRef.current);
      }
      liveFallbackRefreshTimerRef.current = setInterval(() => {
        if (liveRefreshPausedRef.current) {
          return;
        }
        if (typeof document !== "undefined" && document.visibilityState !== "visible") {
          return;
        }
        if (dashboardFetchInFlightRef.current) {
          return;
        }
        bumpRefresh();
      }, DASHBOARD_REFRESH_INTERVAL_MS);
      return () => {
        if (liveFallbackRefreshTimerRef.current) {
          clearInterval(liveFallbackRefreshTimerRef.current);
          liveFallbackRefreshTimerRef.current = null;
        }
      };
    },
    // Refs read via `.current` inside the effect (stable ref objects); match prior provider deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hasSession, liveUpdatesConnected, bumpRefresh],
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
