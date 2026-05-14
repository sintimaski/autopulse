"""Sidebar entries for backend-driven studio routes (`/w/...`).

Add rows here to register more pages.

SYNC REQUIREMENT — every ``page_id`` in ``STUDIO_NAV_PAGES`` (including
demo-only ids such as ``lx_showcase``) must also appear in
``frontend/components/dashboard/studioStaticRoutePageIds.ts``. The dashboard
ships as a Next.js static export, so ``/w/[pageId]`` is pre-rendered via
``generateStaticParams``; a ``page_id`` missing from the frontend allowlist is
never emitted as HTML and 404s at runtime. The frontend test
``studioStaticRoutePageIds.test.ts`` parses this module and fails CI if the two
lists drift apart.
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

# Pages backed by synthetic/demo data only — hidden from the sidebar unless
# ``LUMONOX_STUDIO_SHOWCASE_DEMO`` is on. Real SDK-defined pages go in
# ``STUDIO_NAV_PAGES`` without an entry here.
_DEMO_ONLY_PAGE_IDS: frozenset[str] = frozenset({"lx_showcase"})


def list_studio_nav_pages(*, include_demo: bool = False) -> list[DashboardStudioNavPage]:
    pages = (
        STUDIO_NAV_PAGES
        if include_demo
        else tuple(p for p in STUDIO_NAV_PAGES if p.page_id not in _DEMO_ONLY_PAGE_IDS)
    )
    return sorted(pages, key=lambda p: (p.nav_order, p.page_id))
