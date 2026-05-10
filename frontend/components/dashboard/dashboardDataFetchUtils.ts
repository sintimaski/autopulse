import type { DashboardWidgetsResponse } from "./dashboardTypes";

/** Below this UTF-8 size, send uncompressed JSON (gzip framing often grows tiny payloads). */
export const DASHBOARD_GZIP_JSON_MIN_BYTES = 2048;

const _parsedDashboardFetchTimeout = Number(
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_LUMONOX_DASHBOARD_FETCH_TIMEOUT_MS : NaN,
);
/** Client abort budget for dashboard POSTs; keep aligned with `docs/DASHBOARD_QUERY_LATENCY_CONTRACT.md`. */
export const DASHBOARD_FETCH_TIMEOUT_MS =
  Number.isFinite(_parsedDashboardFetchTimeout) &&
  _parsedDashboardFetchTimeout >= 5_000 &&
  _parsedDashboardFetchTimeout <= 120_000
    ? Math.floor(_parsedDashboardFetchTimeout)
    : 18_000;
export const MAX_WIDGET_POINTS_PER_WIDGET = 240;
export const MAX_WIDGET_POINTS_TOTAL = 2400;
/** Synthetic studio showcase points (`backend/.../studio_showcase.py`); must not lose global trim. */
export const LX_STUDIO_WIDGET_POINT_PREFIX = "lx_studio_";
export const LIVE_REFRESH_THROTTLE_MS = 400;
const _parsedLiveDeltaThrottleMs = Number(
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_LUMONOX_LIVE_DELTA_REFRESH_THROTTLE_MS : NaN,
);
/** Delta-protocol WS events are high-frequency; coalesce into this cadence. */
export const LIVE_DELTA_REFRESH_THROTTLE_MS =
  Number.isFinite(_parsedLiveDeltaThrottleMs) &&
  _parsedLiveDeltaThrottleMs >= 250 &&
  _parsedLiveDeltaThrottleMs <= 10_000
    ? Math.floor(_parsedLiveDeltaThrottleMs)
    : 800;
/** When recent fetches were slow or errored, widen WS-driven refresh spacing. */
export const LIVE_REFRESH_BACKOFF_THROTTLE_MS = 2500;
export const LIVE_REFRESH_BACKOFF_DURATION_MS = 20_000;
/** Elapsed time above this after a successful response triggers WS refresh backoff (below fetch timeout). */
export const LIVE_FETCH_SLOW_MS = 12_000;
export const DASHBOARD_WS_RECONNECT_DELAY_MS = 2_000;
/** When the WS never reaches ``open`` (e.g. HTTP 403 on upgrade), avoid hammering the server every 2s. */
export const DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_BASE_MS = 2_000;
export const DASHBOARD_WS_HANDSHAKE_FAIL_BACKOFF_CAP_MS = 60_000;
export const DASHBOARD_WS_HANDSHAKE_FAIL_EXP_CAP = 5;
export const DASHBOARD_REFRESH_INTERVAL_MS = (() => {
  const raw = process.env.NEXT_PUBLIC_LUMONOX_DASHBOARD_REFRESH_INTERVAL_SECONDS;
  const parsedSeconds = Number(raw);
  if (Number.isFinite(parsedSeconds) && parsedSeconds > 0) {
    return Math.max(1000, Math.floor(parsedSeconds * 1000));
  }
  return 2_000;
})();

export const DASHBOARD_HEAVY_SLICES_REFRESH_INTERVAL_MS = (() => {
  const raw = process.env.NEXT_PUBLIC_LUMONOX_DASHBOARD_HEAVY_REFRESH_INTERVAL_SECONDS;
  const parsedSeconds = Number(raw);
  if (Number.isFinite(parsedSeconds) && parsedSeconds > 0) {
    return Math.max(2_000, Math.floor(parsedSeconds * 1000));
  }
  return 8_000;
})();

/**
 * Overview “stale” red state: no **heavy** home `/dashboard/query` in this long (see `executeDashboardBatchQuery`
 * light/heavy split). Kept above one heavy cadence so normal light-only gaps do not flash red.
 */
export const OVERVIEW_FE_DATA_STALE_AFTER_MS = Math.max(
  Math.ceil(DASHBOARD_HEAVY_SLICES_REFRESH_INTERVAL_MS * 1.25),
  DASHBOARD_REFRESH_INTERVAL_MS * 4,
  8_000,
);

/**
 * Build a `fetch` body + headers for dashboard JSON POSTs. Uses gzip when
 * `CompressionStream` is available and the JSON is large enough to benefit.
 */
export async function buildOptionalGzipJsonRequest(
  value: unknown,
): Promise<{ body: Blob | string; headers: Record<string, string> }> {
  const json = JSON.stringify(value);
  const utf8Bytes = new TextEncoder().encode(json).length;
  const canGzip = typeof CompressionStream !== "undefined" && utf8Bytes >= DASHBOARD_GZIP_JSON_MIN_BYTES;
  if (!canGzip) {
    return { body: json, headers: { "Content-Type": "application/json" } };
  }
  const stream = new CompressionStream("gzip");
  const writer = stream.writable.getWriter();
  await writer.write(new TextEncoder().encode(json));
  await writer.close();
  const compressed = await new Response(stream.readable).arrayBuffer();
  return {
    body: new Blob([compressed]),
    headers: {
      "Content-Type": "application/json",
      "Content-Encoding": "gzip",
    },
  };
}

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
    const maxTotal = MAX_WIDGET_POINTS_TOTAL;
    const infra = merged.filter((p) => p.widget_id.startsWith("infra_"));
    const studio = merged.filter((p) => p.widget_id.startsWith(LX_STUDIO_WIDGET_POINT_PREFIX));
    const rest = merged.filter(
      (p) => !p.widget_id.startsWith("infra_") && !p.widget_id.startsWith(LX_STUDIO_WIDGET_POINT_PREFIX),
    );
    let infraTrimmed = infra;
    if (infraTrimmed.length > maxTotal) {
      infraTrimmed = [...infraTrimmed]
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
        .slice(0, maxTotal);
    }
    // Keep layout-lab synthetic series out of the "newest timestamp wins" pool so busy projects
    // do not evict spread-across-window showcase points.
    if (infraTrimmed.length + studio.length > maxTotal) {
      const infraBudget = Math.max(0, maxTotal - studio.length);
      infraTrimmed = [...infraTrimmed]
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
        .slice(0, infraBudget);
    }
    const budgetForRest = Math.max(0, maxTotal - infraTrimmed.length - studio.length);
    const restKept =
      budgetForRest > 0
        ? [...rest].sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, budgetForRest)
        : [];
    merged = [...infraTrimmed, ...studio, ...restKept].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  }

  return {
    ...payload,
    points: merged,
  };
}
