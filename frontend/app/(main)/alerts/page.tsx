import type { Metadata } from "next";

import { AlertsContent } from "../../../components/dashboard/dashboardPages/AlertsContent";
import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";

export const metadata: Metadata = {
  title: "Alerts",
};

export default function AlertsPage() {
  return (
    <DashboardPageBoundary dataReady="traffic-alerts">
      <AlertsContent />
    </DashboardPageBoundary>
  );
}
