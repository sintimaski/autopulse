import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { DashboardWidgetGalleryContent } from "../../../components/dashboard/dashboardPages/DashboardWidgetGalleryContent";

export const metadata: Metadata = {
  title: "Widgets",
};

export default function WidgetsShowcasePage() {
  return (
    <DashboardPageBoundary dataReady="traffic-requests">
      <DashboardWidgetGalleryContent />
    </DashboardPageBoundary>
  );
}
