/**
 * Page ids emitted as static routes under `/w/[pageId]`.
 *
 * SYNC REQUIREMENT — this list must mirror every `page_id` in
 * `backend/src/lumonox_backend/dashboard/studio_nav_pages.py` (`STUDIO_NAV_PAGES`),
 * including demo-only pages such as `lx_showcase` (gated server-side by
 * `LUMONOX_STUDIO_SHOWCASE_DEMO`). The route still has to be emitted at build
 * time so it exists when the demo flag is on.
 *
 * Why a hand-kept list and not runtime validation: the dashboard ships as a
 * Next.js static export (`output: "export"`). `/w/[pageId]` is pre-rendered via
 * `generateStaticParams`, so a `page_id` that is not in this array produces no
 * HTML file at all — there is no client bundle to run, so it cannot be
 * "validated at runtime" against the bootstrap response. A missing entry just
 * 404s. The sync is therefore enforced by `studioStaticRoutePageIds.test.ts`,
 * which parses the backend module and fails CI on drift.
 */
export const STUDIO_STATIC_ROUTE_PAGE_IDS = ["lx_showcase"] as const;

export type StudioStaticRoutePageId = (typeof STUDIO_STATIC_ROUTE_PAGE_IDS)[number];
