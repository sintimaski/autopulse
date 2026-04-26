import type { Metadata } from "next";

import { LogsContent } from "../../../components/dashboard/dashboardPages/LogsContent";
import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";

export const metadata: Metadata = {
  title: "Logs",
};

export default function LogsPage() {
  return (
    <DashboardPageBoundary>
      <LogsContent />
    </DashboardPageBoundary>
  );
}
