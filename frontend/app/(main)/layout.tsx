import { Suspense, type ReactNode } from "react";

import { DashboardLayoutClient } from "../../components/dashboard/DashboardLayoutClient";

export default function MainLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={null}>
      <DashboardLayoutClient>{children}</DashboardLayoutClient>
    </Suspense>
  );
}
