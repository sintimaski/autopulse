"use client";

import { useEffect, type MutableRefObject } from "react";

import { buildUpdatesWebsocketUrl } from "../dashboardTypes";
import {
  DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_BASE_MS,
  DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_CAP_MS,
  DASHBOARD_WS_HANDSHAKE_FAIL_EXP_CAP,
  LIVE_DELTA_REFRESH_THROTTLE_MS,
  DASHBOARD_WS_RECONNECT_DELAY_MS,
  LIVE_REFRESH_BACKOFF_THROTTLE_MS,
  LIVE_REFRESH_THROTTLE_MS,
} from "../dashboardDataFetchUtils";

const _rawRealtimeWsEnabled =
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_LUMONOX_DASHBOARD_REALTIME_WS_ENABLED : undefined;
const DASHBOARD_REALTIME_WS_ENABLED =
  typeof _rawRealtimeWsEnabled === "string"
    ? !["0", "false", "no", "off"].includes(_rawRealtimeWsEnabled.trim().toLowerCase())
    : true;

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
  liveSnapshotVersionRef: MutableRefObject<number>;
  liveGapRecoveryQueuedRef: MutableRefObject<boolean>;
  liveDeltaProtocolActiveRef: MutableRefObject<boolean>;
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
    liveSnapshotVersionRef,
    liveGapRecoveryQueuedRef,
    liveDeltaProtocolActiveRef,
    bumpRefresh,
  } = options;

  useEffect(
    () => {
    if (!DASHBOARD_REALTIME_WS_ENABLED) {
      queueMicrotask(() => {
        setLiveUpdatesConnected(false);
      });
      liveWsHandshakeFailuresRef.current = 0;
      liveSnapshotVersionRef.current = 0;
      liveGapRecoveryQueuedRef.current = false;
      liveDeltaProtocolActiveRef.current = false;
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
    if (!hasSession || !authSessionResolved) {
      queueMicrotask(() => {
        setLiveUpdatesConnected(false);
      });
      liveWsHandshakeFailuresRef.current = 0;
      liveSnapshotVersionRef.current = 0;
      liveGapRecoveryQueuedRef.current = false;
      liveDeltaProtocolActiveRef.current = false;
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
        : liveDeltaProtocolActiveRef.current
          ? LIVE_DELTA_REFRESH_THROTTLE_MS
          : LIVE_REFRESH_THROTTLE_MS;
    const scheduleLiveRefreshFromWebSocket = (options?: { queueWhenInFlight?: boolean }) => {
      const queueWhenInFlight = options?.queueWhenInFlight ?? true;
      if (liveRefreshPausedRef.current) {
        return;
      }
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return;
      }
      if (dashboardFetchInFlightRef.current) {
        if (queueWhenInFlight) {
          dashboardQueuedRefreshRef.current = true;
        }
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
    const scheduleGapCatchUpRefresh = () => {
      if (liveGapRecoveryQueuedRef.current) {
        return;
      }
      liveGapRecoveryQueuedRef.current = true;
      dashboardQueuedRefreshRef.current = true;
      scheduleLiveRefreshFromWebSocket({ queueWhenInFlight: true });
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
          const subscribe = {
            type: "dashboard.subscribe",
            project_id: sessionProjectId,
            requested_slices: ["overview", "requests", "error_groups", "widgets", "diagnosis"],
          };
          socket.send(JSON.stringify(subscribe));
          if (liveSnapshotVersionRef.current > 0) {
            socket.send(
              JSON.stringify({
                type: "dashboard.resume",
                snapshot_version: liveSnapshotVersionRef.current,
              }),
            );
          }
        };
        socket.onmessage = (event) => {
          if (cancelled) {
            return;
          }
          let parsed: Record<string, unknown> | null = null;
          try {
            parsed = JSON.parse(event.data) as Record<string, unknown>;
          } catch {
            parsed = null;
          }
          const rawType = typeof parsed?.type === "string" ? parsed.type : "";
          if (!rawType) {
            return;
          }
          const payload = parsed ?? {};
          if (rawType === "dashboard.snapshot") {
            liveDeltaProtocolActiveRef.current = true;
            const snapshotVersion =
              typeof payload.snapshot_version === "number" ? payload.snapshot_version : null;
            if (snapshotVersion != null && Number.isFinite(snapshotVersion) && snapshotVersion >= 0) {
              const prev = liveSnapshotVersionRef.current;
              liveSnapshotVersionRef.current = Math.max(prev, snapshotVersion);
              if (snapshotVersion > prev + 1) {
                scheduleGapCatchUpRefresh();
              }
            }
            return;
          }
          if (rawType === "dashboard.delta") {
            liveDeltaProtocolActiveRef.current = true;
            const fromVersion = typeof payload.from_version === "number" ? payload.from_version : null;
            const toVersion = typeof payload.to_version === "number" ? payload.to_version : null;
            if (
              fromVersion == null ||
              toVersion == null ||
              !Number.isFinite(fromVersion) ||
              !Number.isFinite(toVersion)
            ) {
              return;
            }
            const current = liveSnapshotVersionRef.current;
            const hasGap = fromVersion > current;
            liveSnapshotVersionRef.current = Math.max(current, toVersion);
            if (hasGap) {
              scheduleGapCatchUpRefresh();
              return;
            }
            // Server applies ingest to the query snapshot; client refreshes on a light throttle.
            liveGapRecoveryQueuedRef.current = false;
            scheduleLiveRefreshFromWebSocket({ queueWhenInFlight: false });
            return;
          }
          if (rawType === "dashboard.degraded") {
            liveDeltaProtocolActiveRef.current = true;
            scheduleGapCatchUpRefresh();
            return;
          }
          if (rawType === "dashboard_update" || rawType === "ingest") {
            if (liveDeltaProtocolActiveRef.current) {
              return;
            }
            scheduleLiveRefreshFromWebSocket({ queueWhenInFlight: true });
          }
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
      liveGapRecoveryQueuedRef.current = false;
      liveDeltaProtocolActiveRef.current = false;
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
    [
      hasSession,
      authSessionResolved,
      sessionProjectId,
      reloadDashboardAuthSession,
      setLiveUpdatesConnected,
      bumpRefresh,
    ],
  );
}
