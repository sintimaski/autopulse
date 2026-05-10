import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DashboardBackendWidgetGalleryContent } from "../../../../components/dashboard/dashboardPages/DashboardBackendWidgetGalleryContent";
import { DashboardPageBoundary } from "../../../../components/dashboard/DashboardPageBoundary";
import { STUDIO_STATIC_ROUTE_PAGE_IDS } from "../../../../components/dashboard/studioStaticRoutePageIds";

export function generateStaticParams(): { pageId: string }[] {
  return STUDIO_STATIC_ROUTE_PAGE_IDS.map((pageId) => ({ pageId }));
}

export const metadata: Metadata = {
  title: "Studio",
};

export default async function StudioWidgetPage({ params }: { params: Promise<{ pageId: string }> }) {
  const { pageId } = await params;
  if (!(STUDIO_STATIC_ROUTE_PAGE_IDS as readonly string[]).includes(pageId)) {
    notFound();
  }
  return (
    <DashboardPageBoundary dataReady="studio-widgets">
      <DashboardBackendWidgetGalleryContent lockedPageId={pageId} />
    </DashboardPageBoundary>
  );
}
