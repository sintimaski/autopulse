"use client";

import { useEffect, useState } from "react";

import { buildApiUrl } from "./dashboardTypes";

export function useDashboardAuthSession(refreshToken: number): {
  hasSession: boolean;
  authSessionResolved: boolean;
} {
  const [hasSession, setHasSession] = useState(false);
  const [authSessionResolved, setAuthSessionResolved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const response = await fetch(buildApiUrl("/dashboard/auth/session"), {
          credentials: "include",
        });
        if (!response.ok) {
          if (!cancelled) {
            setHasSession(false);
          }
          return;
        }
        const payload = (await response.json()) as { authenticated?: boolean };
        if (!cancelled) {
          setHasSession(Boolean(payload.authenticated));
        }
      } catch {
        if (!cancelled) {
          setHasSession(false);
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
  }, [refreshToken]);

  return { hasSession, authSessionResolved };
}
