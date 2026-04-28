"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { useDashboardData } from "../DashboardDataContext";

export function OnboardingContent() {
  const d = useDashboardData();
  const [message, setMessage] = useState<string | null>(null);
  const hasIssuedApiKey = d.apiKeys.length > 0 || Boolean(d.lastIssuedApiKey);
  const hasFirstEvent = (d.requests?.total ?? 0) > 0 || (d.overview?.request_count ?? 0) > 0;

  const apiKeyPreview = useMemo(() => {
    if (d.lastIssuedApiKey) {
      return d.lastIssuedApiKey;
    }
    if (d.apiKeys[0]) {
      return `${d.apiKeys[0].key_id} (existing key id)`;
    }
    return null;
  }, [d.apiKeys, d.lastIssuedApiKey]);

  return (
    <section className="space-y-4 rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div>
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Time-to-first-value setup</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Complete these three checks to confirm your project is ingesting and visible in the dashboard.
        </p>
      </div>

      <ol className="space-y-3">
        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">1) Issue an ingest API key</p>
          <p className="mt-1 text-sm text-slate-600 dark:text-neutral-300">
            Generate a project key, then copy it into your app environment as `AUTOPULSE_API_KEY`.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={async () => {
                const ok = await d.issueApiKey();
                setMessage(ok ? "New API key issued. Copy it now." : "Failed to issue API key.");
              }}
              className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-900 shadow-sm transition-colors hover:bg-sky-100"
            >
              Issue key
            </button>
            <button
              type="button"
              onClick={() => void d.refreshApiKeys()}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-100 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
            >
              Refresh keys
            </button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasIssuedApiKey
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasIssuedApiKey ? "Completed" : "Pending"}
            </span>
          </div>
          {apiKeyPreview ? (
            <code className="mt-2 block break-all rounded bg-slate-100 px-2 py-1 text-xs dark:bg-neutral-950 dark:text-neutral-200">
              {apiKeyPreview}
            </code>
          ) : null}
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">2) Send your first ingest event</p>
          <p className="mt-1 text-sm text-slate-600 dark:text-neutral-300">
            Trigger a request in your FastAPI app instrumented with the SDK, then refresh once.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => d.setRefreshToken((token) => token + 1)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-100 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
            >
              Refresh status
            </button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasFirstEvent
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasFirstEvent ? "Completed" : "Waiting for first event"}
            </span>
          </div>
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">3) Validate diagnosis surfaces</p>
          <p className="mt-1 text-sm text-slate-600 dark:text-neutral-300">
            Confirm signals are visible in dashboard cards and grouped failures in errors and diagnosis.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <Link href="/dashboard" className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300">
              Open Dashboard
            </Link>
            <span className="text-slate-400">·</span>
            <Link href="/diagnosis" className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300">
              Open Errors & Diagnosis
            </Link>
          </div>
        </li>
      </ol>

      {message ? <p className="text-sm text-slate-600 dark:text-neutral-300">{message}</p> : null}
    </section>
  );
}
