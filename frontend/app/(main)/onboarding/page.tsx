import type { Metadata } from "next";

import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";
import { OnboardingContent } from "../../../components/dashboard/dashboardPages/OnboardingContent";

export const metadata: Metadata = {
  title: "Onboarding",
};

export default function OnboardingPage() {
  return (
    <DashboardPageBoundary dataReady="onboarding">
      <OnboardingContent />
    </DashboardPageBoundary>
  );
}
