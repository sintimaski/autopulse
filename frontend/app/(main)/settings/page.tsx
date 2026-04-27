import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { SettingsContent } from "../../../components/dashboard/dashboardPages/SettingsContent";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <DashboardPageBoundary dataReady="settings-only">
      <SettingsContent />
    </DashboardPageBoundary>
  );
}
