import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { WidgetsShowroomContent } from "../../../components/dashboard/dashboardPages/WidgetsShowroomContent";

export const metadata: Metadata = {
  title: "Widget showroom",
};

export default function WidgetsShowroomPage() {
  return (
    <DashboardPageBoundary dataReady="settings-only">
      <WidgetsShowroomContent />
    </DashboardPageBoundary>
  );
}
