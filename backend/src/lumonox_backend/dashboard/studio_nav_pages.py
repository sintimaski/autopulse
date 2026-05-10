"""Sidebar entries for backend-driven studio routes (`/w/...`).

Add rows here to register more pages. The Next.js static export must list each
``page_id`` in ``frontend/components/dashboard/studioStaticRoutePageIds.ts`` so
the route is emitted at build time.
"""

from __future__ import annotations

from lumonox_backend.schemas.dashboard import DashboardStudioNavPage

STUDIO_NAV_PAGES: tuple[DashboardStudioNavPage, ...] = (
    DashboardStudioNavPage(
        page_id="lx_showcase",
        pathname="/w/lx_showcase",
        sidebar_label="Layout lab",
        page_title="Widget layout lab",
        page_subtitle="Every widget type with varied sections, column spans, and row spans.",
        icon="sparkles",
        nav_section_heading="Studio",
        nav_order=10,
    ),
)


def list_studio_nav_pages() -> list[DashboardStudioNavPage]:
    return sorted(STUDIO_NAV_PAGES, key=lambda p: (p.nav_order, p.page_id))
