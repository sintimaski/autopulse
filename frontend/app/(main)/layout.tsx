import { Suspense, type ReactNode } from "react";

import { DashboardLayoutClient } from "../../components/dashboard/DashboardLayoutClient";
import { DashboardSessionRestoring } from "../../components/dashboard/DashboardPageBoundary";

export default function MainLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <DashboardSessionRestoring
          title="Loading dashboard…"
          message="Resolving route and session context."
        />
      }
    >
      <DashboardLayoutClient>{children}</DashboardLayoutClient>
    </Suspense>
  );
}
