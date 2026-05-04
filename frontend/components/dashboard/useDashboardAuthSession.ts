"use client";

import { useCallback, useEffect, useState } from "react";

import { buildApiUrl, type DashboardSessionResponse } from "./dashboardTypes";

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

export type DashboardAuthSessionIssue = "none" | "unauthorized" | "network";

export function useDashboardAuthSession(): {
  hasSession: boolean;
  authSessionResolved: boolean;
  sessionEmail: string | null;
  membershipRole: DashboardSessionResponse["membership_role"];
  /** Distinguish expired/forbidden session from a connectivity failure when ``hasSession`` is false. */
  sessionIssue: DashboardAuthSessionIssue;
  /** Re-run ``/dashboard/auth/session`` (e.g. after WS handshake failures or HTTP 401) without a full reload. */
  reloadSession: () => void;
} {
  const [hasSession, setHasSession] = useState(false);
  const [authSessionResolved, setAuthSessionResolved] = useState(false);
  const [sessionEmail, setSessionEmail] = useState<string | null>(null);
  const [membershipRole, setMembershipRole] = useState<DashboardSessionResponse["membership_role"]>(null);
  const [sessionIssue, setSessionIssue] = useState<DashboardAuthSessionIssue>("none");
  const [sessionRequestId, setSessionRequestId] = useState(0);

  const reloadSession = useCallback(() => {
    setSessionRequestId((id) => id + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!cancelled) {
        setSessionIssue("none");
      }
      try {
        const response = await fetchSessionWithTimeout(
          buildApiUrl("/dashboard/auth/session"),
          { credentials: "include" },
          DASHBOARD_AUTH_SESSION_TIMEOUT_MS,
        );
        if (!response.ok) {
          if (!cancelled) {
            setHasSession(false);
            setSessionEmail(null);
            setMembershipRole(null);
            setSessionIssue(
              response.status === 401 || response.status === 403 ? "unauthorized" : "network",
            );
          }
          return;
        }
        const payload = (await response.json()) as DashboardSessionResponse;
        if (!cancelled) {
          setHasSession(Boolean(payload.authenticated));
          setSessionEmail(payload.email ?? null);
          setMembershipRole(payload.membership_role ?? null);
          setSessionIssue("none");
        }
      } catch (err) {
        if (!cancelled) {
          setHasSession(false);
          setSessionEmail(null);
          setMembershipRole(null);
          setSessionIssue("network");
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
  }, [sessionRequestId]);

  return { hasSession, authSessionResolved, sessionEmail, membershipRole, sessionIssue, reloadSession };
}
