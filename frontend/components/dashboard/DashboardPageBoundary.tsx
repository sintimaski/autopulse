"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReactNode } from "react";

import { useDashboardData } from "./DashboardDataContext";
import { buildApiUrl } from "./dashboardTypes";

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
      if (!response.ok) {
        throw new Error("Request failed");
      }
      setMessage("If the email is allowed, check your inbox for the sign-in link.");
    } catch {
      setMessage("Unable to send sign-in link. Check backend auth settings.");
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
          Enter your email to request a magic link. Dashboard access is session-first; ingest API keys are only for your app SDK.
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
            This view requires recent traffic data that has not arrived yet. If you are onboarding,
            finish the checklist in{" "}
            <Link
              href="/onboarding"
              className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
            >
              Onboarding
            </Link>{" "}
            to send a first event, then refresh.
          </p>
        </section>
      </div>
    );
  }

  return <div className="mx-auto max-w-[88rem] space-y-6">{children}</div>;
}
