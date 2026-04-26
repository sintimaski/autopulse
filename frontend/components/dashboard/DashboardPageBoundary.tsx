"use client";

import type { ReactNode } from "react";

import { useDashboardData } from "./DashboardDataContext";

export function ApiKeyMissing() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-4 py-14 text-slate-100">
      <div className="mx-auto max-w-lg rounded-2xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-slate-950/50 backdrop-blur">
        <p className="text-sm font-medium uppercase tracking-widest text-sky-300/90">AutoPulse</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-3 text-sm leading-relaxed text-slate-300">
          Set <code className="rounded bg-black/30 px-1.5 py-0.5">NEXT_PUBLIC_AUTOPULSE_API_KEY</code> and{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5">NEXT_PUBLIC_AUTOPULSE_API_BASE_URL</code> in{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5">frontend/.env.local</code>, then restart{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5">npm run dev</code>.
        </p>
      </div>
    </main>
  );
}

export function DashboardPageBoundary({ children }: { children: ReactNode }) {
  const d = useDashboardData();

  if (d.loading) {
    return (
      <div className="mx-auto max-w-5xl">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-600 shadow-sm">
          <p className="text-sm font-medium">Loading dashboard data...</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="h-20 animate-pulse rounded-xl bg-slate-100" />
            <div className="h-20 animate-pulse rounded-xl bg-slate-100" />
            <div className="h-20 animate-pulse rounded-xl bg-slate-100" />
          </div>
        </section>
      </div>
    );
  }

  if (d.errorMessage) {
    return (
      <div className="mx-auto max-w-5xl">
        <section
          className="rounded-2xl border border-rose-200 bg-rose-50/90 p-6 text-rose-900 shadow-sm"
          role="alert"
        >
          <h2 className="text-lg font-semibold">Unable to load data</h2>
          <p className="mt-2 text-sm">{d.errorMessage}</p>
          <p className="mt-2 text-xs text-rose-700/90">
            Verify API key and backend URL, then use Refresh in the header.
          </p>
        </section>
      </div>
    );
  }

  if (!d.overview || !d.requests || !d.errorGroups) {
    return null;
  }

  return <div className="mx-auto max-w-5xl space-y-6">{children}</div>;
}
