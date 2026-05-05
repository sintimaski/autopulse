import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { QueryExplorerContent } from "../../../components/dashboard/dashboardPages/QueryExplorerContent";

export const metadata: Metadata = {
  title: "Query Explorer",
};

export default function QueryExplorerPage() {
  return (
    <DashboardPageBoundary dataReady="traffic-requests">
      <QueryExplorerContent />
    </DashboardPageBoundary>
  );
}
