"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { useDashboardData } from "../DashboardDataContext";
import { isEmbeddedRelativeDashboard } from "../dashboardTypes";

export function OnboardingContent() {
  const d = useDashboardData();
  const embedded = isEmbeddedRelativeDashboard();
  const [message, setMessage] = useState<string | null>(null);
  const status = d.onboardingStatus;
  const hasIssuedApiKey = status?.ingest_key_ready ?? (d.apiKeys.length > 0 || Boolean(d.lastIssuedApiKey));
  const hasFirstEvent =
    status?.first_event_received ?? ((d.requests?.total ?? 0) > 0 || (d.overview?.request_count ?? 0) > 0);
  const hasDiagnosisSignal = status?.first_diagnostic_signal_ready ?? false;

  const apiKeyPreview = useMemo(() => {
    if (d.lastIssuedApiKey) return d.lastIssuedApiKey;
    if (d.apiKeys[0]) return `${d.apiKeys[0].key_id} (existing)`;
    return null;
  }, [d.apiKeys, d.lastIssuedApiKey]);

  return (
    <section className="space-y-4 rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div>
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Onboarding</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          {embedded
            ? "First SDK boot writes .env.autopulse (ingest + Next public keys). Source it before building static UI, then restart once."
            : "Put the issued key in your app as AUTOPULSE_API_KEY and set AUTOPULSE_INGEST_URL to /ingest on your backend."}
        </p>
      </div>

      <ol className="space-y-3">
        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">1. Session</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">Signed in with magic link.</p>
          <span className="mt-2 inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            Done
          </span>
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">2. Ingest key</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
            {embedded
              ? "Issue below only if you want a new token; dashboard auto-syncs .env.autopulse. Rebuild UI after key changes."
              : "Issue, then copy into host env as AUTOPULSE_API_KEY."}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={async () => {
                const ok = await d.issueApiKey();
                setMessage(
                  ok
                    ? embedded
                      ? "Issued — .env.autopulse synced automatically. Rebuild UI + restart host."
                      : "Issued — copy into host env and restart app."
                    : "Issue failed.",
                );
              }}
              className="ap-btn-primary"
            >
              Issue key
            </button>
            <button type="button" onClick={() => void d.refreshApiKeys()} className="ap-btn">
              Refresh
            </button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasIssuedApiKey
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasIssuedApiKey ? "OK" : "…"}
            </span>
          </div>
          {apiKeyPreview ? (
            <code className="mt-2 block break-all rounded bg-slate-100 px-2 py-1 text-xs dark:bg-neutral-950 dark:text-neutral-200">
              {apiKeyPreview}
            </code>
          ) : null}
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">3. First ingest</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
            {embedded
              ? "Embedded sends one startup request after boot (disable with AUTOPULSE_EMBEDDED_STARTUP_INGEST=0). Refresh here."
              : "Send traffic through your instrumented app, then refresh."}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => d.setRefreshToken((t) => t + 1)} className="ap-btn">
              Refresh
            </button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasFirstEvent
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasFirstEvent ? "OK" : "…"}
            </span>
          </div>
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">4. Errors</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">When traffic includes failures, open Diagnosis.</p>
          <div className="mt-2 flex flex-wrap gap-2 text-sm">
            <Link href="/dashboard" className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300">
              Overview
            </Link>
            <span className="text-slate-400">·</span>
            <Link href="/diagnosis" className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300">
              Diagnosis
            </Link>
          </div>
          <span
            className={`mt-2 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
              hasDiagnosisSignal
                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
            }`}
          >
            {hasDiagnosisSignal ? "OK" : "…"}
          </span>
        </li>
      </ol>

      {message ? <p className="text-xs text-slate-600 dark:text-neutral-400">{message}</p> : null}
    </section>
  );
}
