"use client";

import { sanitizeRumPath, sanitizeRumStack, sanitizeRumText } from "./rumSanitize";

const RUM_ENABLED = process.env.NEXT_PUBLIC_LUMONOX_RUM_ENABLED === "1";
const RUM_ENDPOINT =
  process.env.NEXT_PUBLIC_LUMONOX_RUM_ENDPOINT?.trim() || "/lumonox/rum";
const RUM_DEBUG = process.env.NEXT_PUBLIC_LUMONOX_RUM_DEBUG === "1";
const RUM_SAMPLE_RATE = (() => {
  const raw = process.env.NEXT_PUBLIC_LUMONOX_RUM_SAMPLE_RATE;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return 1;
  }
  return Math.max(0, Math.min(1, parsed));
})();

export type RumEventType =
  | "route_view"
  | "runtime_error"
  | "unhandled_rejection"
  | "session_performance"
  | "diagnosis_activation"
  | "modal_lifecycle"
  | "filter_zero_results"
  | "empty_state_cta"
  | "jobs_primary_action";

type RumEventPayload = {
  type: RumEventType;
  path: string;
  session_id: string;
  ts: string;
  data: Record<string, string | number | boolean | null>;
};

let sessionCache: { sessionId: string; sampled: boolean } | null = null;

function buildSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `rum-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function ensureRumSession(): { sessionId: string; sampled: boolean } | null {
  if (!RUM_ENABLED) {
    return null;
  }
  if (!sessionCache) {
    sessionCache = {
      sessionId: buildSessionId(),
      sampled: Math.random() <= RUM_SAMPLE_RATE,
    };
  }
  return sessionCache;
}

function sendRumEvent(endpoint: string, payload: RumEventPayload): void {
  const body = JSON.stringify(payload);
  if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    try {
      navigator.sendBeacon(endpoint, body);
      return;
    } catch {
      /* quiet */
    }
  }
  void fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
    credentials: "same-origin",
  }).catch(() => {
    /* quiet */
  });
}

/**
 * Emit a sampled RUM event when `NEXT_PUBLIC_LUMONOX_RUM_ENABLED=1`.
 * Uses the same session + sample draw as `RumClient` route views.
 */
export function emitRumEvent(
  type: RumEventType,
  data: Record<string, string | number | boolean | null>,
  pathOverride?: string,
): void {
  const session = ensureRumSession();
  if (!session?.sampled) {
    return;
  }
  const rawPath =
    pathOverride ??
    (typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : "/");
  const payload: RumEventPayload = {
    type,
    path: sanitizeRumPath(rawPath),
    session_id: session.sessionId,
    ts: new Date().toISOString(),
    data,
  };
  if (RUM_DEBUG) {
    console.info("[lumonox-rum]", payload);
  }
  sendRumEvent(RUM_ENDPOINT, payload);
}

export function isRumClientSampled(): boolean {
  return Boolean(ensureRumSession()?.sampled);
}

export function emitRumRuntimeError(message: string, stack: string | null | undefined): void {
  emitRumEvent("runtime_error", {
    message: sanitizeRumText(message || "runtime error"),
    stack: sanitizeRumStack(stack),
  });
}

export function emitRumUnhandledRejection(message: string, stack: string | null | undefined): void {
  emitRumEvent("unhandled_rejection", {
    message: sanitizeRumText(message),
    stack: sanitizeRumStack(stack),
  });
}

export function emitRumSessionPerformance(data: Record<string, string | number | boolean | null>): void {
  emitRumEvent("session_performance", data);
}

export function emitRumRouteView(pathForPayload: string): void {
  const safe = sanitizeRumPath(pathForPayload);
  emitRumEvent("route_view", { route: safe }, safe);
}
