import type { DashboardWidgetsResponse } from "./dashboardTypes";

export const DASHBOARD_FETCH_TIMEOUT_MS = 12_000;
export const MAX_WIDGET_POINTS_PER_WIDGET = 240;
export const MAX_WIDGET_POINTS_TOTAL = 2400;
export const LIVE_REFRESH_THROTTLE_MS = 400;
/** When recent fetches were slow or errored, widen WS-driven refresh spacing. */
export const LIVE_REFRESH_BACKOFF_THROTTLE_MS = 2500;
export const LIVE_REFRESH_BACKOFF_DURATION_MS = 20_000;
/** Elapsed time above this after a successful response triggers WS refresh backoff. */
export const LIVE_FETCH_SLOW_MS = 7000;
export const DASHBOARD_WS_RECONNECT_DELAY_MS = 2_000;
export const DASHBOARD_REFRESH_INTERVAL_MS = (() => {
  const raw = process.env.NEXT_PUBLIC_AUTOPULSE_DASHBOARD_REFRESH_INTERVAL_SECONDS;
  const parsedSeconds = Number(raw);
  if (Number.isFinite(parsedSeconds) && parsedSeconds > 0) {
    return Math.max(250, Math.floor(parsedSeconds * 1000));
  }
  return 5_000;
})();

export function fetchWithTimeout(
  input: string,
  init: RequestInit,
  timeoutMs: number,
  parentSignal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController();
  const onParentAbort = () => {
    controller.abort(parentSignal?.reason);
  };
  if (parentSignal) {
    if (parentSignal.aborted) {
      controller.abort(parentSignal.reason);
    } else {
      parentSignal.addEventListener("abort", onParentAbort, { once: true });
    }
  }
  const timeoutId = window.setTimeout(() => {
    controller.abort(new DOMException("Dashboard request timed out", "AbortError"));
  }, timeoutMs);
  return fetch(input, { ...init, signal: controller.signal }).finally(() => {
    window.clearTimeout(timeoutId);
    if (parentSignal) {
      parentSignal.removeEventListener("abort", onParentAbort);
    }
  });
}

export function trimDashboardWidgetPayload(payload: DashboardWidgetsResponse): DashboardWidgetsResponse {
  const grouped = new Map<string, DashboardWidgetsResponse["points"]>();
  for (const point of payload.points ?? []) {
    const bucket = grouped.get(point.widget_id);
    if (bucket) {
      bucket.push(point);
    } else {
      grouped.set(point.widget_id, [point]);
    }
  }

  let merged: DashboardWidgetsResponse["points"] = [];
  for (const widgetId of grouped.keys()) {
    const points = grouped.get(widgetId) ?? [];
    points.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    const recent =
      points.length > MAX_WIDGET_POINTS_PER_WIDGET
        ? points.slice(points.length - MAX_WIDGET_POINTS_PER_WIDGET)
        : points;
    merged = merged.concat(recent);
  }

  if (merged.length > MAX_WIDGET_POINTS_TOTAL) {
    merged.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    merged = merged.slice(0, MAX_WIDGET_POINTS_TOTAL);
    merged.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  }

  return {
    ...payload,
    points: merged,
  };
}
