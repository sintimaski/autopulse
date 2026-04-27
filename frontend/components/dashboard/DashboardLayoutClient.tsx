"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { DashboardAppShell } from "./AppShell";
import { ApiKeyMissing } from "./DashboardPageBoundary";
import { DashboardDataProvider, useDashboardData } from "./DashboardDataContext";
import { ServerQueryToolbar } from "./ServerQueryToolbar";

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Dashboard",
    subtitle: "Volume and headline rates for the selected window.",
  },
  "/diagnosis": {
    title: "Diagnosis",
    subtitle: "Error signals and grouped stack signatures.",
  },
  "/alerts": {
    title: "Alerts",
    subtitle: "Heuristic preview and backend job runbook.",
  },
  "/logs": {
    title: "Logs",
    subtitle: "Scope traffic fast, then inspect request-level evidence.",
  },
};

function ShellWithData({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const d = useDashboardData();
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stored = window.localStorage.getItem("autopulse-theme");
      if (stored === "dark") {
        setIsDark(true);
        return;
      }
      if (stored === "light") {
        setIsDark(false);
        return;
      }
      setIsDark(window.matchMedia("(prefers-color-scheme: dark)").matches);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    window.localStorage.setItem("autopulse-theme", isDark ? "dark" : "light");
  }, [isDark]);

  if (!d.hasApiKey) {
    return <ApiKeyMissing />;
  }

  const meta = PAGE_META[pathname] ?? PAGE_META["/dashboard"];
  const showServerScope = pathname === "/dashboard" || pathname === "/diagnosis" || pathname === "/logs";
  const resetServerFilters = () => {
    d.onServerMethodChange("ALL");
    d.onServerStatusClassChange("ALL");
    d.setPathQuery("");
    d.setMinLatencyMs("");
    d.setMaxLatencyMs("");
    d.setServerEnvironmentQuery("");
    d.setServerServiceQuery("");
    d.setRequestPage(0);
    d.setErrorGroupPage(0);
  };

  return (
    <DashboardAppShell
      pathname={pathname}
      title={meta.title}
      subtitle={meta.subtitle}
      isDark={isDark}
      onToggleTheme={() => setIsDark((prev) => !prev)}
      onRefresh={() => d.setRefreshToken((n) => n + 1)}
      filterToolbarAutoCollapse={showServerScope}
      filterToolbarCompactLabel="Server scope"
      onResetServerFilters={showServerScope ? resetServerFilters : undefined}
      filterToolbar={showServerScope ? <ServerQueryToolbar /> : null}
    >
      {children}
    </DashboardAppShell>
  );
}

export function DashboardLayoutClient({ children }: { children: ReactNode }) {
  return (
    <DashboardDataProvider>
      <ShellWithData>{children}</ShellWithData>
    </DashboardDataProvider>
  );
}
