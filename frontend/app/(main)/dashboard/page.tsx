import type { Metadata } from "next";

import { DashboardHomeContent } from "../../../components/dashboard/dashboardPages/DashboardHomeContent";
import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default function DashboardPage() {
  return (
    <DashboardPageBoundary>
      <DashboardHomeContent />
    </DashboardPageBoundary>
  );
}
