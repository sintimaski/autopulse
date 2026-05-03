"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReactNode } from "react";

import { useDashboardData } from "./DashboardDataContext";
import type { DashboardMagicLinkRequestResponse } from "./dashboardTypes";
import { buildApiUrl, isEmbeddedRelativeDashboard } from "./dashboardTypes";

/** Shown while `/dashboard/auth/session` is in flight so we do not flash the sign-in screen on reload. */
export function DashboardSessionRestoring() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-100 px-4 text-slate-600 dark:bg-neutral-950 dark:text-neutral-400">
      <div
        className="h-9 w-9 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600 dark:border-neutral-600 dark:border-t-sky-400"
        aria-hidden
      />
      <p className="text-sm font-medium text-slate-700 dark:text-neutral-300">Checking your session…</p>
    </div>
  );
}

export function ApiKeyMissing() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const requestMagicLink = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(buildApiUrl("/dashboard/auth/magic-link/request"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const raw = await response.text();
      let parsed: unknown = null;
      try {
        parsed = raw ? JSON.parse(raw) : null;
      } catch {
        parsed = null;
      }
      if (!response.ok) {
        const detail =
          parsed &&
          typeof parsed === "object" &&
          parsed !== null &&
          "detail" in parsed
            ? String((parsed as { detail: unknown }).detail)
            : raw.slice(0, 240);
        setMessage(
          `Request failed (${response.status}). ${detail || "See browser Network tab and backend logs."} ` +
            "Typical fixes: set DASHBOARD_AUTH_ALLOWED_EMAIL to this address (or use dev allowlist), " +
            "ensure ALERT_EMAIL_PROVIDER + keys/outbox for delivery, add your UI origin to CORS_ALLOW_ORIGINS " +
            "if the API is on another host/port, and set NEXT_PUBLIC_AUTOPULSE_API_BASE_URL to a path " +
            "(e.g. /autopulse) when UI and API share one origin.",
        );
        return;
      }
      if (!parsed || typeof parsed !== "object" || parsed === null || !("accepted" in parsed)) {
        setMessage("Unexpected response from server (not JSON). Check API base URL and backend logs.");
        return;
      }
      const okPayload = parsed as DashboardMagicLinkRequestResponse;
      if (okPayload.dev_magic_link_url) {
        setMessage(`Dev link: ${okPayload.dev_magic_link_url}`);
      } else if (okPayload.dev_token) {
        setMessage(`Dev token: ${okPayload.dev_token}`);
      } else {
        setMessage("If the email is allowed, check your inbox for the sign-in link.");
      }
    } catch (err) {
      const hint =
        err instanceof TypeError
          ? "Network error (wrong API URL, CORS, or server down). For embedded UI use NEXT_PUBLIC_AUTOPULSE_API_BASE_URL=/autopulse unless API is on another origin."
          : err instanceof Error
            ? err.message
            : String(err);
      setMessage(`Unable to reach sign-in API. ${hint}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-4 py-14 text-slate-100">
      <div className="mx-auto max-w-lg rounded-2xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-slate-950/50 backdrop-blur">
        <p className="text-sm font-medium uppercase tracking-widest text-slate-400/90">AutoPulse</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Dashboard sign in</h1>
        <p className="mt-3 text-sm leading-relaxed text-slate-300">
          Enter your email for a magic link. Session-first.
          {isEmbeddedRelativeDashboard() ? (
            <>
              {" "}
              Static UI reads <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[0.7rem]">.env.autopulse</code> (see onboarding).
            </>
          ) : (
            <> SDK keys are for your app, not this screen.</>
          )}
        </p>
        <div className="mt-5 space-y-3">
          <label className="block">
            <span className="sr-only">Email for magic link sign-in</span>
            <input
              className="w-full rounded-lg border border-white/20 bg-black/25 px-3 py-2 text-sm text-white placeholder:text-slate-400"
              type="email"
              autoComplete="email"
              value={email}
              placeholder="you@example.com"
              aria-label="Email address"
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="w-full rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-slate-950 disabled:opacity-60"
            onClick={() => void requestMagicLink()}
            disabled={loading || !email.trim()}
          >
            Request magic link
          </button>
        </div>
        {message ? (
          <p className="mt-4 text-xs text-slate-200" role="status" aria-live="polite">
            {message}
          </p>
        ) : null}
      </div>
    </main>
  );
}

export type DashboardPageDataReady =
  /** Overview home & Diagnosis (error groups + extended breakdown). */
  | "traffic-full"
  /** Logs: request table + window metadata from overview. */
  | "traffic-requests"
  /** Alerts: sparkline + dispatches (no error-group list). */
  | "traffic-alerts"
  /** Settings: project JSON only (no traffic bundle). */
  | "settings-only"
  /** Onboarding: always allow children to render; no traffic required. */
  | "onboarding";

export function DashboardPageBoundary({
  children,
  dataReady = "traffic-full",
}: {
  children: ReactNode;
  dataReady?: DashboardPageDataReady;
}) {
  const d = useDashboardData();
  const hasRenderableData =
    dataReady === "traffic-full"
      ? Boolean(d.overview && d.requests && d.errorGroups)
      : dataReady === "traffic-requests" || dataReady === "traffic-alerts"
        ? Boolean(d.overview && d.requests)
        : dataReady === "onboarding"
          ? true
          : Boolean(d.alertSettings && d.retentionSettings);

  if (d.loading) {
    return (
      <div className="mx-auto max-w-[88rem]">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-600 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300">
          <p className="text-sm font-medium">Loading dashboard data...</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="h-20 animate-pulse rounded-xl bg-slate-100 dark:bg-neutral-800" />
            <div className="h-20 animate-pulse rounded-xl bg-slate-100 dark:bg-neutral-800" />
            <div className="h-20 animate-pulse rounded-xl bg-slate-100 dark:bg-neutral-800" />
          </div>
        </section>
      </div>
    );
  }

  if (d.errorMessage && !hasRenderableData) {
    return (
      <div className="mx-auto max-w-[88rem]">
        <section
          className="rounded-2xl border border-rose-200 bg-rose-50/90 p-6 text-rose-900 shadow-sm dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-100"
          role="alert"
        >
          <h2 className="text-lg font-semibold">Unable to load data</h2>
          <p className="mt-2 text-sm">{d.errorMessage}</p>
          <p className="mt-2 text-xs text-rose-700/90 dark:text-rose-300/90">
            Verify dashboard sign-in, backend URL, adjust scope filters, or reload the page.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-lg bg-rose-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-900 dark:bg-rose-200 dark:text-rose-950 dark:hover:bg-white"
              onClick={() => d.setRefreshToken((t) => t + 1)}
            >
              Retry fetch
            </button>
          </div>
        </section>
      </div>
    );
  }

  if (!hasRenderableData) {
    // Fall-through empty state so pages never render a blank main column.
    // Happens when a slice endpoint returned 200 but with nothing renderable
    // (e.g. new project with no traffic yet) and no error was reported.
    return (
      <div className="mx-auto max-w-[88rem]">
        <section
          className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-600 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300"
          role="status"
          aria-live="polite"
        >
          <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">
            No data for this view yet
          </h2>
          <p className="mt-2 text-sm">
            This view requires recent traffic data that has not arrived yet. If you are onboarding, open{" "}
            <Link
              href="/onboarding"
              className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
            >
              Onboarding
            </Link>
            {isEmbeddedRelativeDashboard()
              ? " — embedded startup ping after host boot; refresh."
              : " — send traffic, refresh."}
          </p>
        </section>
      </div>
    );
  }

  return <div className="mx-auto max-w-[88rem] space-y-6">{children}</div>;
}
