"use client";

import { useEffect, useState } from "react";

import { buildApiUrl } from "./dashboardTypes";

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
        const response = await fetch(buildApiUrl("/dashboard/auth/session"), {
          credentials: "include",
        });
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
