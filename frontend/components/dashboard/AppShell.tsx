"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import {
  Activity,
  Bell,
  LayoutDashboard,
  LayoutGrid,
  PanelLeft,
  PanelLeftClose,
  Rocket,
  RotateCw,
  Settings,
  Stethoscope,
  ScrollText,
} from "../../lib/icons";
import type { LucideIcon } from "../../lib/icons";
import { AutoCollapsibleHeaderPanel } from "./AutoCollapsibleHeaderPanel";
import { isEmbeddedRelativeDashboard } from "./dashboardTypes";

const SIDEBAR_COLLAPSED_KEY = "autopulse.sidebarCollapsed";

type NavItem = { href: string; label: string; Icon: LucideIcon };

const BASE_NAV: readonly NavItem[] = [
  { href: "/dashboard", label: "Overview", Icon: LayoutDashboard },
  { href: "/widgets-showcase", label: "Widget gallery", Icon: LayoutGrid },
  { href: "/requests", label: "Requests", Icon: ScrollText },
  { href: "/alerts", label: "Alerts", Icon: Bell },
  { href: "/diagnosis", label: "Errors & Diagnosis", Icon: Stethoscope },
  { href: "/settings", label: "Settings", Icon: Settings },
] as const;

const ONBOARDING_NAV: NavItem = {
  href: "/onboarding",
  label: "Onboarding",
  Icon: Rocket,
};

export function DashboardAppShell({
  children,
  onRefresh,
  filterToolbar,
  filterToolbarAutoCollapse = false,
  filterToolbarCompactLabel = "Server scope",
  onResetServerFilters,
  pathname,
  title,
  subtitle,
  statusStrip,
  isDark,
  diagnosisNavQuery = "",
  logsNavQuery = "",
  showOnboardingNav = false,
}: {
  children: ReactNode;
  /** Omitted to hide the header control (live data is driven by WebSocket + scope changes). */
  onRefresh?: () => void;
  filterToolbar: ReactNode | null;
  filterToolbarAutoCollapse?: boolean;
  filterToolbarCompactLabel?: string;
  onResetServerFilters?: () => void;
  pathname: string;
  title: string;
  subtitle: string;
  statusStrip?: ReactNode;
  isDark: boolean;
  /** Last persisted or live `/diagnosis` server-scope query string (without `?`). */
  diagnosisNavQuery?: string;
  /** Last persisted or live `/logs` server-scope query string (without `?`). */
  logsNavQuery?: string;
  /** Show the Onboarding link while onboarding is incomplete. */
  showOnboardingNav?: boolean;
}) {
  const nav: readonly NavItem[] = showOnboardingNav ? [ONBOARDING_NAV, ...BASE_NAV] : BASE_NAV;
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
      if (raw === "1") {
        queueMicrotask(() => setSidebarCollapsed(true));
      }
    } catch {
      /* ignore */
    }
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const sidebarWidth = sidebarCollapsed ? "4.5rem" : "14rem";

  return (
    <div suppressHydrationWarning className={isDark ? "dark" : ""}>
      <div
        className="flex min-h-screen bg-gradient-to-b from-slate-100 via-slate-100 to-slate-200/70 text-slate-900 dark:from-neutral-950 dark:via-neutral-950 dark:to-neutral-900 dark:text-neutral-100"
        style={{ ["--dashboard-sidebar-width" as string]: sidebarWidth }}
      >
        <aside
          className="sticky top-0 flex h-screen w-[var(--dashboard-sidebar-width)] shrink-0 flex-col border-r border-neutral-800/80 bg-neutral-950/95 text-neutral-100 shadow-xl shadow-neutral-950/20 backdrop-blur transition-[width] duration-200 ease-out dark:border-neutral-800 dark:bg-neutral-900/95"
          aria-label="Primary navigation"
        >
          <div className="border-b border-white/10 px-2 py-4 sm:px-3">
            {sidebarCollapsed ? (
              <div className="flex flex-col items-center gap-2">
                <Activity
                  className="size-7 text-sky-400/90 dark:text-sky-400/80"
                  aria-hidden
                />
                <button
                  type="button"
                  onClick={toggleSidebar}
                  aria-label="Expand sidebar"
                  className="rounded-lg p-2 text-neutral-300 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:focus-visible:ring-neutral-500/50"
                >
                  <PanelLeft className="size-4" aria-hidden />
                </button>
              </div>
            ) : (
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1 px-1">
                  <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-sky-400/90 dark:text-neutral-400">
                    <Activity className="size-3.5 shrink-0 text-sky-400/90 dark:text-sky-400/70" aria-hidden />
                    AutoPulse
                  </p>
                  <p className="mt-1 text-sm font-semibold tracking-tight">Console</p>
                </div>
                <button
                  type="button"
                  onClick={toggleSidebar}
                  aria-label="Collapse sidebar to icons"
                  className="shrink-0 rounded-lg p-2 text-neutral-300 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:focus-visible:ring-neutral-500/50"
                >
                  <PanelLeftClose className="size-4" aria-hidden />
                </button>
              </div>
            )}
          </div>
          <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-4 text-sm">
            {nav.map((item) => {
              const active = pathname === item.href;
              const Icon = item.Icon;
              return (
                <Link
                  key={item.href}
                  prefetch={false}
                  href={
                    item.href === "/diagnosis" && diagnosisNavQuery
                      ? `${item.href}?${diagnosisNavQuery}`
                      : (item.href === "/logs" || item.href === "/requests") && logsNavQuery
                        ? `${item.href}?${logsNavQuery}`
                        : item.href
                  }
                  title={sidebarCollapsed ? item.label : undefined}
                  aria-current={active ? "page" : undefined}
                  aria-label={sidebarCollapsed ? item.label : undefined}
                  className={`flex items-center gap-3 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:focus-visible:ring-neutral-500/50 ${
                    sidebarCollapsed ? "justify-center px-2 py-2.5" : "px-3 py-2"
                  } ${
                    active
                      ? "bg-white/15 font-medium text-white"
                      : "text-neutral-300 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <Icon className="size-[1.125rem] shrink-0" aria-hidden />
                  {!sidebarCollapsed ? <span>{item.label}</span> : null}
                </Link>
              );
            })}
          </nav>
          {!sidebarCollapsed ? (
            <div className="border-t border-white/10 px-4 py-3 text-xs leading-snug text-neutral-500">
              FastAPI-native visibility. Tune scope, then inspect evidence.
            </div>
          ) : (
            <div className="border-t border-white/10 py-2" aria-hidden />
          )}
        </aside>

        <div className="flex min-w-0 flex-1 flex-col transition-[margin] duration-200">
          <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/85">
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
              <div>
                <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-neutral-100 sm:text-2xl">
                  {title}
                </h1>
                <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">{subtitle}</p>
              </div>
              {onRefresh ? (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onRefresh}
                    title="Refresh"
                    aria-label="Refresh"
                    className="ap-btn shrink-0 p-2"
                  >
                    <RotateCw className="size-4" aria-hidden />
                  </button>
                </div>
              ) : null}
            </div>
            {statusStrip ? <div className="border-t border-slate-200/80 px-4 py-2.5 dark:border-neutral-800 sm:px-6">{statusStrip}</div> : null}
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

          <footer className="border-t border-slate-200/80 bg-white/85 px-4 py-4 text-center text-sm text-slate-500 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/80 dark:text-neutral-400 sm:px-6">
            <span className="text-slate-600 dark:text-neutral-300">AutoPulse</span>
            {" — "}
            Ingest at{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-neutral-800">
              POST /ingest
            </code>
            {" · "}
            {isEmbeddedRelativeDashboard() ? (
              <>
                Embedded: <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-neutral-800">.env.autopulse</code> + startup ingest
                ping.
              </>
            ) : (
              <>Events are scoped to your project API key.</>
            )}
          </footer>
        </div>
      </div>
    </div>
  );
}
