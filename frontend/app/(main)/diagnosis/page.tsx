import type { Metadata } from "next";

import { DiagnosisContent } from "../../../components/dashboard/dashboardPages/DiagnosisContent";
import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";

export const metadata: Metadata = {
  title: "Diagnosis",
};

export default function DiagnosisPage() {
  return (
    <DashboardPageBoundary>
      <DiagnosisContent />
    </DashboardPageBoundary>
  );
}
