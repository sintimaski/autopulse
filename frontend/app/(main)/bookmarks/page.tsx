import type { Metadata } from "next";

import { BookmarksContent } from "../../../components/dashboard/dashboardPages/BookmarksContent";
import { DashboardPageBoundary } from "../../../components/dashboard/DashboardPageBoundary";

export const metadata: Metadata = {
  title: "Bookmarks",
};

export default function BookmarksPage() {
  return (
    <DashboardPageBoundary dataReady="settings-only">
      <BookmarksContent />
    </DashboardPageBoundary>
  );
}
