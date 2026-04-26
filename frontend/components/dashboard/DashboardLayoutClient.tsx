"use client";

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
    subtitle: "Request rows with client-side filters.",
  },
};

function ShellWithData({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const d = useDashboardData();

  if (!d.hasApiKey) {
    return <ApiKeyMissing />;
  }

  const meta = PAGE_META[pathname] ?? PAGE_META["/dashboard"];

  return (
    <DashboardAppShell
      pathname={pathname}
      title={meta.title}
      subtitle={meta.subtitle}
      onRefresh={() => d.setRefreshToken((n) => n + 1)}
      filterToolbar={<ServerQueryToolbar />}
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
