"use client";

import Link from "next/link";
import type { ReactNode } from "react";

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/diagnosis", label: "Diagnosis" },
  { href: "/alerts", label: "Alerts" },
  { href: "/logs", label: "Logs" },
] as const;

export function DashboardAppShell({
  children,
  onRefresh,
  filterToolbar,
  pathname,
  title,
  subtitle,
}: {
  children: ReactNode;
  onRefresh: () => void;
  filterToolbar: ReactNode;
  pathname: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex min-h-screen bg-slate-100 text-slate-900">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-slate-200/90 bg-slate-950 text-slate-100">
        <div className="border-b border-white/10 px-4 py-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-sky-400/90">AutoPulse</p>
          <p className="mt-1 text-sm font-semibold tracking-tight">Console</p>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-4 text-sm">
          {nav.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-2 transition ${
                  active ? "bg-white/15 font-medium text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-white/10 px-4 py-3 text-[11px] leading-snug text-slate-500">
          FastAPI-native visibility. Tune the query bar to refetch all panels.
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-slate-200/90 bg-white/95 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-slate-900 sm:text-xl">{title}</h1>
              <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm transition hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>
          <div className="border-t border-slate-100 bg-slate-50/90 px-4 py-3 sm:px-6">{filterToolbar}</div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6">{children}</main>

        <footer className="border-t border-slate-200/90 bg-white px-4 py-4 text-center text-xs text-slate-500 sm:px-6">
          <span className="text-slate-600">AutoPulse</span>
          {" — "}
          Ingest at <code className="rounded bg-slate-100 px-1 py-0.5 text-[11px]">POST /ingest</code>
          {" · "}
          Events are scoped to your project API key.
        </footer>
      </div>
    </div>
  );
}
