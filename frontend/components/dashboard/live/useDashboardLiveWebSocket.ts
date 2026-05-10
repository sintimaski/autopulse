"use client";

import { useEffect, type MutableRefObject } from "react";

import { buildUpdatesWebsocketUrl } from "../dashboardTypes";
import {
  DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_BASE_MS,
  DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_CAP_MS,
  DASHBOARD_WS_HANDSHAKE_FAIL_EXP_CAP,
  DASHBOARD_WS_RECONNECT_DELAY_MS,
  LIVE_REFRESH_BACKOFF_THROTTLE_MS,
  LIVE_REFRESH_THROTTLE_MS,
} from "../dashboardDataFetchUtils";

export type UseDashboardLiveWebSocketOptions = {
  hasSession: boolean;
  authSessionResolved: boolean;
  /** Included so reconnect runs when the active project changes. */
  sessionProjectId: string | null;
  reloadDashboardAuthSession: () => void;
  setLiveUpdatesConnected: (connected: boolean) => void;
  liveWsBackoffUntilRef: MutableRefObject<number>;
  liveRefreshPausedRef: MutableRefObject<boolean>;
  dashboardFetchInFlightRef: MutableRefObject<boolean>;
  dashboardQueuedRefreshRef: MutableRefObject<boolean>;
  liveLastRefreshAtRef: MutableRefObject<number>;
  livePendingRefreshTimerRef: MutableRefObject<ReturnType<typeof setTimeout> | null>;
  liveReconnectTimerRef: MutableRefObject<ReturnType<typeof setTimeout> | null>;
  liveSocketRef: MutableRefObject<WebSocket | null>;
  liveWsHandshakeFailuresRef: MutableRefObject<number>;
  bumpRefresh: () => void;
};

/**
 * Dashboard updates WebSocket: connect, throttle refresh bumps, reconnect with backoff.
 * Extracted from `DashboardDataProvider` to keep the context file smaller.
 */
export function useDashboardLiveWebSocket(options: UseDashboardLiveWebSocketOptions): void {
  const {
    hasSession,
    authSessionResolved,
    sessionProjectId,
    reloadDashboardAuthSession,
    setLiveUpdatesConnected,
    liveWsBackoffUntilRef,
    liveRefreshPausedRef,
    dashboardFetchInFlightRef,
    dashboardQueuedRefreshRef,
    liveLastRefreshAtRef,
    livePendingRefreshTimerRef,
    liveReconnectTimerRef,
    liveSocketRef,
    liveWsHandshakeFailuresRef,
    bumpRefresh,
  } = options;

  useEffect(
    () => {
    if (!hasSession || !authSessionResolved) {
      queueMicrotask(() => {
        setLiveUpdatesConnected(false);
      });
      liveWsHandshakeFailuresRef.current = 0;
      dashboardQueuedRefreshRef.current = false;
      if (liveReconnectTimerRef.current) {
        clearTimeout(liveReconnectTimerRef.current);
        liveReconnectTimerRef.current = null;
      }
      if (livePendingRefreshTimerRef.current) {
        clearTimeout(livePendingRefreshTimerRef.current);
        livePendingRefreshTimerRef.current = null;
      }
      if (liveSocketRef.current) {
        liveSocketRef.current.close();
        liveSocketRef.current = null;
      }
      return;
    }
    let cancelled = false;
    const wsThrottleMs = () =>
      Date.now() < liveWsBackoffUntilRef.current
        ? LIVE_REFRESH_BACKOFF_THROTTLE_MS
        : LIVE_REFRESH_THROTTLE_MS;
    const scheduleLiveRefreshFromWebSocket = () => {
      if (liveRefreshPausedRef.current) {
        return;
      }
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return;
      }
      if (dashboardFetchInFlightRef.current) {
        dashboardQueuedRefreshRef.current = true;
        return;
      }
      const now = Date.now();
      const throttleMs = wsThrottleMs();
      const elapsedMs = now - liveLastRefreshAtRef.current;
      if (elapsedMs < throttleMs) {
        if (livePendingRefreshTimerRef.current) {
          return;
        }
        const delayMs = Math.max(1, throttleMs - elapsedMs);
        livePendingRefreshTimerRef.current = setTimeout(() => {
          livePendingRefreshTimerRef.current = null;
          if (liveRefreshPausedRef.current) {
            return;
          }
          if (typeof document !== "undefined" && document.visibilityState !== "visible") {
            return;
          }
          liveLastRefreshAtRef.current = Date.now();
          bumpRefresh();
        }, delayMs);
        return;
      }
      if (livePendingRefreshTimerRef.current) {
        clearTimeout(livePendingRefreshTimerRef.current);
        livePendingRefreshTimerRef.current = null;
      }
      liveLastRefreshAtRef.current = now;
      if (!liveRefreshPausedRef.current) {
        bumpRefresh();
      }
    };
    const connect = () => {
      if (cancelled) {
        return;
      }
      try {
        let opened = false;
        const socket = new WebSocket(buildUpdatesWebsocketUrl());
        liveSocketRef.current = socket;
        socket.onopen = () => {
          if (cancelled) {
            socket.close();
            return;
          }
          opened = true;
          liveWsHandshakeFailuresRef.current = 0;
          setLiveUpdatesConnected(true);
        };
        socket.onmessage = (event) => {
          if (cancelled) {
            return;
          }
          let parsed: { type?: string } | null = null;
          try {
            parsed = JSON.parse(event.data) as { type?: string };
          } catch {
            parsed = null;
          }
          if (!parsed?.type) {
            return;
          }
          if (parsed.type !== "dashboard_update" && parsed.type !== "ingest") {
            return;
          }
          scheduleLiveRefreshFromWebSocket();
        };
        socket.onclose = (event: CloseEvent) => {
          if (cancelled) {
            return;
          }
          setLiveUpdatesConnected(false);
          if (liveReconnectTimerRef.current) {
            clearTimeout(liveReconnectTimerRef.current);
          }
          const authRejected = !opened || event.code === 1008;
          if (authRejected) {
            liveWsHandshakeFailuresRef.current += 1;
            if (liveWsHandshakeFailuresRef.current === 2) {
              reloadDashboardAuthSession();
            }
          } else {
            liveWsHandshakeFailuresRef.current = 0;
          }
          const failures = liveWsHandshakeFailuresRef.current;
          const delayMs =
            failures > 0
              ? Math.min(
                  DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_CAP_MS,
                  DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_BASE_MS *
                    2 ** Math.min(failures - 1, DASHBOARD_WS_HANDSHAKE_FAIL_EXP_CAP),
                )
              : DASHBOARD_WS_RECONNECT_DELAY_MS;
          liveReconnectTimerRef.current = setTimeout(() => {
            connect();
          }, delayMs);
        };
        socket.onerror = () => {
          // onclose handles reconnect/fallback.
        };
      } catch {
        setLiveUpdatesConnected(false);
      }
    };
    connect();
    return () => {
      cancelled = true;
      setLiveUpdatesConnected(false);
      dashboardQueuedRefreshRef.current = false;
      if (liveReconnectTimerRef.current) {
        clearTimeout(liveReconnectTimerRef.current);
        liveReconnectTimerRef.current = null;
      }
      if (livePendingRefreshTimerRef.current) {
        clearTimeout(livePendingRefreshTimerRef.current);
        livePendingRefreshTimerRef.current = null;
      }
      if (liveSocketRef.current) {
        liveSocketRef.current.close();
        liveSocketRef.current = null;
      }
    };
    },
    // Refs read via `.current` (stable identities); match prior provider deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hasSession, authSessionResolved, sessionProjectId, reloadDashboardAuthSession, setLiveUpdatesConnected, bumpRefresh],
  );
}
