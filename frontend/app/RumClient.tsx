"use client";

import { usePathname } from "next/navigation";
import { useEffect, useMemo } from "react";

import { sanitizeRumPath, sanitizeRumStack, sanitizeRumText } from "../lib/rumSanitize";

type RumEventPayload = {
  type: "route_view" | "runtime_error" | "unhandled_rejection" | "session_performance";
  path: string;
  session_id: string;
  ts: string;
  data: Record<string, string | number | boolean | null>;
};

const RUM_ENABLED = process.env.NEXT_PUBLIC_AUTOPULSE_RUM_ENABLED === "1";
const RUM_ENDPOINT =
  process.env.NEXT_PUBLIC_AUTOPULSE_RUM_ENDPOINT?.trim() || "/autopulse/rum";
const RUM_DEBUG = process.env.NEXT_PUBLIC_AUTOPULSE_RUM_DEBUG === "1";
const RUM_SAMPLE_RATE = (() => {
  const raw = process.env.NEXT_PUBLIC_AUTOPULSE_RUM_SAMPLE_RATE;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return 1;
  }
  return Math.max(0, Math.min(1, parsed));
})();
const RUM_CLIENT_SAMPLED = Math.random() <= RUM_SAMPLE_RATE;
const RUM_CLIENT_SESSION_ID = buildSessionId();

function buildSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `rum-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function sendRumEvent(endpoint: string, payload: RumEventPayload): void {
  const body = JSON.stringify(payload);
  if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    try {
      navigator.sendBeacon(endpoint, body);
      return;
    } catch {
      // Quiet failure by default.
    }
  }
  void fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
    credentials: "same-origin",
  }).catch(() => {
    // Quiet failure by default.
  });
}

export function RumClient() {
  const pathname = usePathname() ?? "/";
  const enabled = useMemo(() => {
    if (!RUM_ENABLED) {
      return false;
    }
    return true;
  }, []);

  useEffect(() => {
    if (!enabled || !RUM_CLIENT_SAMPLED) {
      return;
    }
    const safePath = sanitizeRumPath(pathname);
    const emit = (
      type: RumEventPayload["type"],
      data: RumEventPayload["data"],
      eventPath = safePath,
    ) => {
      const payload: RumEventPayload = {
        type,
        path: eventPath,
        session_id: RUM_CLIENT_SESSION_ID,
        ts: new Date().toISOString(),
        data,
      };
      if (RUM_DEBUG) {
        // Debug mode is explicit; keep logs concise and scrubbed.
        console.info("[autopulse-rum]", payload);
      }
      sendRumEvent(RUM_ENDPOINT, payload);
    };

    emit("route_view", { route: safePath });
  }, [enabled, pathname]);

  useEffect(() => {
    if (!enabled || !RUM_CLIENT_SAMPLED) {
      return;
    }
    const emit = (type: RumEventPayload["type"], data: RumEventPayload["data"], eventPath = pathname) => {
      sendRumEvent(RUM_ENDPOINT, {
        type,
        path: sanitizeRumPath(eventPath),
        session_id: RUM_CLIENT_SESSION_ID,
        ts: new Date().toISOString(),
        data,
      });
    };

    const navigationEntry = performance
      .getEntriesByType("navigation")
      .find((entry): entry is PerformanceNavigationTiming => entry instanceof PerformanceNavigationTiming);
    if (navigationEntry) {
      emit("session_performance", {
        dom_content_loaded_ms: Number(navigationEntry.domContentLoadedEventEnd.toFixed(1)),
        load_event_ms: Number(navigationEntry.loadEventEnd.toFixed(1)),
      });
    }

    const onError = (event: ErrorEvent) => {
      emit("runtime_error", {
        message: sanitizeRumText(event.message || "runtime error"),
        stack: sanitizeRumStack(event.error?.stack),
      });
    };
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const message =
        typeof reason === "string"
          ? reason
          : reason instanceof Error
            ? reason.message
            : "unhandled promise rejection";
      const stack = reason instanceof Error ? reason.stack : null;
      emit("unhandled_rejection", {
        message: sanitizeRumText(message),
        stack: sanitizeRumStack(stack),
      });
    };

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, [enabled, pathname]);

  return null;
}
