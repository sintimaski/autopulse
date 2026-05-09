"use client";

import { usePathname } from "next/navigation";
import { useEffect, useMemo } from "react";

import { sanitizeRumPath } from "../lib/rumSanitize";
import {
  emitRumRouteView,
  emitRumRuntimeError,
  emitRumSessionPerformance,
  emitRumUnhandledRejection,
  isRumClientSampled,
} from "../lib/rumRuntime";

const RUM_ENABLED = process.env.NEXT_PUBLIC_AUTOPULSE_RUM_ENABLED === "1";

export function RumClient() {
  const pathname = usePathname() ?? "/";
  const enabled = useMemo(() => RUM_ENABLED, []);

  useEffect(() => {
    if (!enabled || !isRumClientSampled()) {
      return;
    }
    const safePath = sanitizeRumPath(pathname);
    emitRumRouteView(safePath);
  }, [enabled, pathname]);

  useEffect(() => {
    if (!enabled || !isRumClientSampled()) {
      return;
    }

    const navigationEntry = performance
      .getEntriesByType("navigation")
      .find((entry): entry is PerformanceNavigationTiming => entry instanceof PerformanceNavigationTiming);
    if (navigationEntry) {
      emitRumSessionPerformance({
        dom_content_loaded_ms: Number(navigationEntry.domContentLoadedEventEnd.toFixed(1)),
        load_event_ms: Number(navigationEntry.loadEventEnd.toFixed(1)),
      });
    }

    const onError = (event: ErrorEvent) => {
      emitRumRuntimeError(event.message || "runtime error", event.error?.stack);
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
      emitRumUnhandledRejection(message, stack);
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
