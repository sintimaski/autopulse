import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { IncidentWorkspaceContent } from "../../../components/dashboard/dashboardPages/IncidentWorkspaceContent";

export const metadata: Metadata = {
  title: "Incident",
};

export default function IncidentPage() {
  return (
    <DashboardPageBoundary dataReady="traffic-requests">
      <IncidentWorkspaceContent />
    </DashboardPageBoundary>
  );
}
