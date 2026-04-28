"use client";

import { useEffect, useState } from "react";

import { buildApiUrl } from "./dashboardTypes";

export function useDashboardAuthSession(refreshToken: number): {
  hasApiKey: boolean;
  authSessionResolved: boolean;
} {
  const [hasApiKey, setHasApiKey] = useState(false);
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
            setHasApiKey(false);
          }
          return;
        }
        const payload = (await response.json()) as { authenticated?: boolean };
        if (!cancelled) {
          setHasApiKey(Boolean(payload.authenticated));
        }
      } catch {
        if (!cancelled) {
          setHasApiKey(false);
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

  return { hasApiKey, authSessionResolved };
}
