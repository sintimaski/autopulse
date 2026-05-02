"use client";

import { useEffect, useState } from "react";

import { buildApiUrl } from "./dashboardTypes";

const DASHBOARD_AUTH_SESSION_TIMEOUT_MS = 12_000;

function fetchSessionWithTimeout(
  input: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => {
    controller.abort(new DOMException("Dashboard auth session timed out", "AbortError"));
  }, timeoutMs);
  return fetch(input, { ...init, signal: controller.signal }).finally(() => {
    window.clearTimeout(timeoutId);
  });
}

export function useDashboardAuthSession(): {
  hasSession: boolean;
  authSessionResolved: boolean;
  sessionEmail: string | null;
} {
  const [hasSession, setHasSession] = useState(false);
  const [authSessionResolved, setAuthSessionResolved] = useState(false);
  const [sessionEmail, setSessionEmail] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const response = await fetchSessionWithTimeout(
          buildApiUrl("/dashboard/auth/session"),
          { credentials: "include" },
          DASHBOARD_AUTH_SESSION_TIMEOUT_MS,
        );
        if (!response.ok) {
          if (!cancelled) {
            setHasSession(false);
          }
          return;
        }
        const payload = (await response.json()) as {
          authenticated?: boolean;
          email?: string | null;
        };
        if (!cancelled) {
          setHasSession(Boolean(payload.authenticated));
          setSessionEmail(payload.email ?? null);
        }
      } catch {
        if (!cancelled) {
          setHasSession(false);
          setSessionEmail(null);
        }
      } finally {
        if (!cancelled) {
          setAuthSessionResolved(true);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  return { hasSession, authSessionResolved, sessionEmail };
}
