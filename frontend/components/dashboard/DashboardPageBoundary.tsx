"use client";

import Link from "next/link";
import { useContext, useState } from "react";
import type { ReactNode } from "react";

import { OnboardingCompletionNudge } from "./OnboardingCompletionNudge";
import { DashboardInitialLoadGrid } from "../ui/DashboardInitialLoadGrid";
import { CardSpinner, dashboardSpinnerRingClassName } from "../ui/CardSpinner";
import { DashboardDataContext, useDashboardData } from "./DashboardDataContext";
import type { DashboardMagicLinkRequestResponse } from "./dashboardTypes";
import { buildApiUrl, isAbsoluteOriginOnlyApiBase, isApiSubpathDashboard } from "./dashboardTypes";

/** Shown while `/dashboard/auth/session` is in flight so we do not flash the sign-in screen on reload. */
export function DashboardSessionRestoring({
  title = "Checking your session…",
  message,
}: {
  title?: string;
  message?: string;
} = {}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-100 px-4 py-10 text-slate-600 dark:bg-neutral-950 dark:text-neutral-400">
      <div
        className="w-full max-w-md rounded-2xl border border-slate-200/90 bg-white p-8 text-center shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
        role="status"
        aria-label={title}
        aria-busy="true"
        aria-live="polite"
      >
        <div className={`mx-auto h-9 w-9 ${dashboardSpinnerRingClassName}`} aria-hidden />
        <p className="mt-4 text-sm font-medium text-slate-800 dark:text-neutral-200">{title}</p>
        {message ? (
          <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-neutral-500">{message}</p>
        ) : null}
      </div>
    </div>
  );
}

export function ApiKeyMissing() {
  const dashboardCtx = useContext(DashboardDataContext);
  const sessionIssue = dashboardCtx?.dashboardAuthSessionIssue ?? "none";
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
            "if the API is on another host/port, and set NEXT_PUBLIC_LUMONOX_API_BASE_URL to the API origin " +
            "(e.g. http://127.0.0.1:8000 for standalone backend; leave unset for same-origin /dashboard paths)." +
            (response.status === 404 && isAbsoluteOriginOnlyApiBase()
              ? " 404 here often means an extra path segment (e.g. …/lumonox/dashboard/…): use http://127.0.0.1:8000 with no /lumonox prefix for the default backend."
              : ""),
        );
        return;
      }
      if (!parsed || typeof parsed !== "object" || parsed === null || !("accepted" in parsed)) {
        setMessage("Unexpected response from server (not JSON). Check API base URL and backend logs.");
        return;
      }
      const okPayload = parsed as DashboardMagicLinkRequestResponse;
      const showDevAuthHints = process.env.NODE_ENV === "development";
      if (okPayload.dev_magic_link_url && showDevAuthHints) {
        setMessage(`Dev link: ${okPayload.dev_magic_link_url}`);
      } else if (okPayload.dev_token && showDevAuthHints) {
        setMessage(`Dev token: ${okPayload.dev_token}`);
      } else {
        setMessage("If the email is allowed, check your inbox for the sign-in link.");
      }
    } catch (err) {
      const hint =
        err instanceof TypeError
          ? "Network error (wrong API URL, CORS, or server down). For static UI on the API host use NEXT_PUBLIC_LUMONOX_API_BASE_URL=http://127.0.0.1:8000 (origin only) or leave unset for same-origin /dashboard calls."
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
        <p className="text-sm font-medium uppercase tracking-widest text-slate-400/90">Lumonox</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Dashboard sign in</h1>
        <p className="mt-3 text-sm leading-relaxed text-slate-300">
          Enter your email for a magic link. Session-first.
          {isApiSubpathDashboard() ? (
            <>
              {" "}
              Static UI reads <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[0.7rem]">.env.lumonox</code> (see onboarding).
            </>
          ) : (
            <> SDK keys are for your app, not this screen.</>
          )}
        </p>
        {sessionIssue === "unauthorized" ? (
          <p
            className="mt-4 rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
            role="status"
            aria-live="polite"
          >
            Your dashboard session has ended. Request a new magic link below.
          </p>
        ) : null}
        {sessionIssue === "network" ? (
          <p
            className="mt-4 rounded-lg border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-100"
            role="alert"
            aria-live="polite"
          >
            Could not reach the server to verify your session. Check the API URL, VPN, and that the
            backend is running.
          </p>
        ) : null}
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
  /**
   * Studio `/w/...` widget pages: synthetic showcase data ships in the widgets slice.
   * Allow render once that payload exists, not only when overview+requests are hydrated
   * (avoids “No data for this view yet” while the layout lab is loading or traffic is empty).
   */
  | "studio-widgets"
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
  const onboarding = d.onboardingStatus;
  const bootstrapIssue = d.workspaceBootstrapError;
  const likelyMissingIngestKey = Boolean(onboarding && !onboarding.ingest_key_ready);
  const likelyMissingFirstEvent = Boolean(
    onboarding && onboarding.ingest_key_ready && !onboarding.first_event_received,
  );
  const widgetPayloadReady =
    (d.dashboardWidgets?.definitions?.length ?? 0) > 0 || (d.dashboardWidgets?.points?.length ?? 0) > 0;
  const hasRenderableData =
    dataReady === "traffic-full"
      ? Boolean(d.overview && d.requests && d.errorGroups)
      : dataReady === "traffic-requests" || dataReady === "traffic-alerts"
        ? Boolean(d.overview && d.requests)
        : dataReady === "studio-widgets"
          ? Boolean((d.overview && d.requests) || widgetPayloadReady)
          : dataReady === "onboarding"
            ? true
            : Boolean(d.alertSettings && d.retentionSettings);

  if (d.loading && !hasRenderableData) {
    return (
      <div className="mx-auto max-w-[88rem] space-y-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-500">
          Loading dashboard
        </p>
        {dataReady === "onboarding" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <CardSpinner size="compact" label="Workspace" />
            <CardSpinner size="compact" label="Session & projects" />
          </div>
        ) : (
          <DashboardInitialLoadGrid
            dataReady={
              dataReady === "studio-widgets"
                ? "studio-widgets"
                : dataReady === "settings-only"
                  ? "settings-only"
                  : dataReady === "traffic-alerts"
                    ? "traffic-alerts"
                    : dataReady === "traffic-full"
                      ? "traffic-full"
                      : "traffic-requests"
            }
          />
        )}
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
          {bootstrapIssue ? (
            <p className="mt-2 text-sm">
              Dashboard bootstrap failed before traffic queries completed: {bootstrapIssue}. Verify backend
              readiness (`/health`, `/ready`) and confirm `NEXT_PUBLIC_LUMONOX_API_BASE_URL` points to
              the API origin
              {isAbsoluteOriginOnlyApiBase()
                ? " (origin-only URL detected)."
                : " (prefer origin-only URL for standalone backend)."}
            </p>
          ) : likelyMissingIngestKey ? (
            <p className="mt-2 text-sm">
              No project ingest key is ready yet. Issue a key in{" "}
              <Link
                href="/onboarding"
                className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
              >
                Onboarding
              </Link>{" "}
              (or `Settings` for existing projects), add it as `LUMONOX_API_KEY`, then send a request.
            </p>
          ) : likelyMissingFirstEvent ? (
            <p className="mt-2 text-sm">
              Ingest key exists, but no events were received for this project yet. Check that your app
              sends to backend `POST /ingest`, confirm `LUMONOX_INGEST_URL` points at the correct backend,
              and verify the key belongs to this dashboard project.
            </p>
          ) : (
            <p className="mt-2 text-sm">
              This view requires recent traffic data that has not arrived yet. If you are onboarding, open{" "}
              <Link
                href="/onboarding"
                className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
              >
                Onboarding
              </Link>
              {isApiSubpathDashboard()
                ? " — startup ping may appear after deploy; refresh."
                : " — send traffic, refresh."}
            </p>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[88rem] space-y-6">
      <OnboardingCompletionNudge />
      {children}
    </div>
  );
}
