"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { Activity, PanelLeft, PanelLeftClose, RotateCw } from "../../lib/icons";
import { AutoCollapsibleHeaderPanel } from "./AutoCollapsibleHeaderPanel";
import { DASHBOARD_NAV_SECTIONS } from "./dashboardNavConfig";
import type { DashboardStudioNavPage } from "./dashboardTypes";
import { isApiSubpathDashboard } from "./dashboardTypes";
import { NavIaMigrationBanner } from "./NavIaMigrationBanner";
import { resolveStudioNavIcon } from "./studioNavSidebarIcons";

const SIDEBAR_COLLAPSED_KEY = "lumonox.sidebarCollapsed";

function groupStudioNavBySection(pages: readonly DashboardStudioNavPage[]) {
  const sorted = [...pages].sort((a, b) => a.nav_order - b.nav_order || a.page_id.localeCompare(b.page_id));
  const sections: { heading: string; items: DashboardStudioNavPage[] }[] = [];
  for (const page of sorted) {
    const heading = page.nav_section_heading?.trim() || "Studio";
    const last = sections[sections.length - 1];
    if (last && last.heading === heading) {
      last.items.push(page);
    } else {
      sections.push({ heading, items: [page] });
    }
  }
  return sections;
}

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
  /** Non-blocking alert (e.g. bootstrap retry) shown under the page title. */
  topBanner,
  isDark,
  diagnosisNavQuery = "",
  logsNavQuery = "",
  studioNavPages,
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
  topBanner?: ReactNode;
  isDark: boolean;
  /** Last persisted or live `/diagnosis` server-scope query string (without `?`). */
  diagnosisNavQuery?: string;
  /** Last persisted or live `/logs` server-scope query string (without `?`). */
  logsNavQuery?: string;
  /** Backend-driven `/w/...` entries from `GET /dashboard/bootstrap`. */
  studioNavPages?: readonly DashboardStudioNavPage[];
}) {
  const studioNav = studioNavPages ?? [];
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

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    document.documentElement.classList.toggle("dark", isDark);
    // Do not remove `dark` on cleanup: paint-blocking script in `app/layout.tsx` owns first paint;
    // stripping here caused flashes (StrictMode re-mount, brief unmounts) and white reload frames.
  }, [isDark]);

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
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-sky-600 focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:outline-none focus:ring-2 focus:ring-sky-400/80"
      >
        Skip to main content
      </a>
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
                    Lumonox
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
          {!sidebarCollapsed ? <NavIaMigrationBanner /> : null}
          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-4 text-sm">
            {DASHBOARD_NAV_SECTIONS.map((section, sectionIndex) => (
              <div
                key={section.id}
                className={sectionIndex > 0 ? "mt-1 border-t border-white/10 pt-2" : undefined}
                role="group"
                aria-label={
                  section.heading
                    ? section.heading
                    : section.id === "primary"
                      ? "Diagnosis and workspace"
                      : section.id === "settings"
                        ? "Configuration"
                        : "Navigation"
                }
              >
                {!sidebarCollapsed && section.heading ? (
                  <p className="mb-1 px-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                    {section.heading}
                  </p>
                ) : null}
                <div className="flex flex-col gap-0.5">
                  {section.items.map((item) => {
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
                </div>
              </div>
            ))}
            {studioNav.length
              ? groupStudioNavBySection(studioNav).map((studioSection) => (
                  <div
                    key={studioSection.heading}
                    className="mt-1 border-t border-white/10 pt-2"
                    role="group"
                    aria-label={studioSection.heading}
                  >
                    {!sidebarCollapsed ? (
                      <p className="mb-1 px-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                        {studioSection.heading}
                      </p>
                    ) : null}
                    <div className="flex flex-col gap-0.5">
                      {studioSection.items.map((item) => {
                        const active = pathname === item.pathname;
                        const Icon = resolveStudioNavIcon(item.icon);
                        return (
                          <Link
                            key={item.pathname}
                            prefetch={false}
                            href={item.pathname}
                            title={sidebarCollapsed ? item.sidebar_label : undefined}
                            aria-current={active ? "page" : undefined}
                            aria-label={sidebarCollapsed ? item.sidebar_label : undefined}
                            className={`flex items-center gap-3 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:focus-visible:ring-neutral-500/50 ${
                              sidebarCollapsed ? "justify-center px-2 py-2.5" : "px-3 py-2"
                            } ${
                              active
                                ? "bg-white/15 font-medium text-white"
                                : "text-neutral-300 hover:bg-white/10 hover:text-white"
                            }`}
                          >
                            <Icon className="size-[1.125rem] shrink-0" aria-hidden />
                            {!sidebarCollapsed ? <span>{item.sidebar_label}</span> : null}
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                ))
              : null}
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
              <div className="min-w-0 flex-1">
                <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-neutral-100 sm:text-2xl">
                  {title}
                </h1>
                <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">{subtitle}</p>
                {topBanner ? <div className="mt-3">{topBanner}</div> : null}
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

          <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 max-w-full px-4 py-6 outline-none sm:px-6">
            {children}
          </main>

          <footer className="border-t border-slate-200/80 bg-white/85 px-4 py-4 text-center text-sm text-slate-500 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/80 dark:text-neutral-400 sm:px-6">
            <span className="text-slate-600 dark:text-neutral-300">Lumonox</span>
            {" — "}
            Ingest at{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-neutral-800">
              POST /ingest
            </code>
            {" · "}
            {isApiSubpathDashboard() ? (
              <>
                Local UI bundle: <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-neutral-800">.env.lumonox</code>
                ping.
              </>
            ) : (
              <>Events are scoped to your project ingest API key.</>
            )}
          </footer>
        </div>
      </div>
    </div>
  );
}
