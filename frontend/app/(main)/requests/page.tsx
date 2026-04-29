import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { LogsContent } from "../../../components/dashboard/dashboardPages/LogsContent";

export const metadata: Metadata = {
  title: "Requests",
};

export default function RequestsPage() {
  return (
    <DashboardPageBoundary dataReady="traffic-requests">
      <LogsContent />
    </DashboardPageBoundary>
  );
}
