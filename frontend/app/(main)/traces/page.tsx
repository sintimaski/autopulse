import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { TracesContent } from "../../../components/dashboard/dashboardPages/TracesContent";

export const metadata: Metadata = {
  title: "Traces",
};

export default function TracesPage() {
  return (
    <DashboardPageBoundary dataReady="onboarding">
      <TracesContent />
    </DashboardPageBoundary>
  );
}
