/**
 * Page ids emitted as static routes under `/w/[pageId]`.
 * Keep in sync with `backend/src/lumonox_backend/dashboard/studio_nav_pages.py`.
 */
export const STUDIO_STATIC_ROUTE_PAGE_IDS = ["lx_showcase"] as const;

export type StudioStaticRoutePageId = (typeof STUDIO_STATIC_ROUTE_PAGE_IDS)[number];
