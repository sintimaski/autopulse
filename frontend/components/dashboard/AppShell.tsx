"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AutoCollapsibleHeaderPanel } from "./AutoCollapsibleHeaderPanel";

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/diagnosis", label: "Diagnosis" },
  { href: "/alerts", label: "Alerts" },
  { href: "/logs", label: "Logs" },
] as const;

export function DashboardAppShell({
  children,
  onRefresh,
  onToggleTheme,
  filterToolbar,
  filterToolbarAutoCollapse = false,
  filterToolbarCompactLabel = "Server scope",
  onResetServerFilters,
  pathname,
  title,
  subtitle,
  isDark,
}: {
  children: ReactNode;
  onRefresh: () => void;
  onToggleTheme: () => void;
  filterToolbar: ReactNode | null;
  filterToolbarAutoCollapse?: boolean;
  filterToolbarCompactLabel?: string;
  onResetServerFilters?: () => void;
  pathname: string;
  title: string;
  subtitle: string;
  isDark: boolean;
}) {
  return (
    <div suppressHydrationWarning className={isDark ? "dark" : ""}>
      <div className="flex min-h-screen bg-slate-100 text-slate-900 dark:bg-neutral-950 dark:text-neutral-100">
        <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-neutral-800/90 bg-neutral-950 text-neutral-100 dark:border-neutral-800 dark:bg-neutral-900">
          <div className="border-b border-white/10 px-4 py-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-sky-400/90 dark:text-neutral-400">
              AutoPulse
            </p>
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
                    active
                      ? "bg-white/15 font-medium text-white"
                      : "text-neutral-300 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="border-t border-white/10 px-4 py-3 text-[11px] leading-snug text-neutral-500">
            FastAPI-native visibility. Tune the query bar to refetch all panels.
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-slate-200/90 bg-white/95 dark:border-neutral-800 dark:bg-neutral-900/95">
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
              <div>
                <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-neutral-100 sm:text-xl">
                  {title}
                </h1>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-neutral-400">{subtitle}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onToggleTheme}
                  className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm transition hover:bg-slate-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
                >
                  {isDark ? "Light theme" : "Dark theme"}
                </button>
                <button
                  type="button"
                  onClick={onRefresh}
                  className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm transition hover:bg-slate-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
                >
                  Refresh
                </button>
              </div>
            </div>
            {filterToolbar ? (
              <AutoCollapsibleHeaderPanel
                enabled={filterToolbarAutoCollapse}
                compactLabel={filterToolbarCompactLabel}
                onResetFilters={onResetServerFilters}
              >
                {filterToolbar}
              </AutoCollapsibleHeaderPanel>
            ) : null}
          </header>

          <main className="flex-1 px-4 py-6 sm:px-6">{children}</main>

          <footer className="border-t border-slate-200/90 bg-white px-4 py-4 text-center text-xs text-slate-500 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400 sm:px-6">
            <span className="text-slate-600 dark:text-neutral-300">AutoPulse</span>
            {" — "}
            Ingest at{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-[11px] dark:bg-neutral-800">
              POST /ingest
            </code>
            {" · "}
            Events are scoped to your project API key.
          </footer>
        </div>
      </div>
    </div>
  );
}
