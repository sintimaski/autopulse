import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { STUDIO_STATIC_ROUTE_PAGE_IDS } from "./studioStaticRoutePageIds";

/**
 * W4 — keep the static-route allowlist in sync with the backend studio nav list.
 *
 * `/w/[pageId]` is pre-rendered via `generateStaticParams` from
 * `STUDIO_STATIC_ROUTE_PAGE_IDS`. The backend registers studio pages in
 * `studio_nav_pages.py` (`STUDIO_NAV_PAGES`). A backend page that is missing
 * from the frontend allowlist is never emitted as HTML and silently 404s, so
 * this test fails CI on drift instead of leaving it to manual review.
 */
const here = dirname(fileURLToPath(import.meta.url));
const backendNavPagesPath = resolve(
  here,
  "../../../backend/src/lumonox_backend/dashboard/studio_nav_pages.py",
);

function backendStudioNavPageIds(): string[] {
  const source = readFileSync(backendNavPagesPath, "utf8");
  // Scope to the STUDIO_NAV_PAGES tuple so unrelated `page_id=` strings (e.g.
  // the _DEMO_ONLY_PAGE_IDS frozenset) do not leak into the comparison.
  const tupleMatch = source.match(/STUDIO_NAV_PAGES[^=]*=\s*\(([\s\S]*?)\n\)/);
  if (!tupleMatch) {
    throw new Error(`Could not locate STUDIO_NAV_PAGES tuple in ${backendNavPagesPath}`);
  }
  const ids = [...tupleMatch[1].matchAll(/page_id\s*=\s*"([^"]+)"/g)].map((m) => m[1]);
  if (ids.length === 0) {
    throw new Error(`Parsed zero page_id entries from ${backendNavPagesPath}`);
  }
  return ids;
}

describe("studioStaticRoutePageIds", () => {
  it("mirrors every backend STUDIO_NAV_PAGES page_id (incl. demo-only ids)", () => {
    const backendIds = [...backendStudioNavPageIds()].sort();
    const frontendIds = [...STUDIO_STATIC_ROUTE_PAGE_IDS].sort();
    expect(frontendIds).toEqual(backendIds);
  });

  it("has no duplicate entries", () => {
    expect(new Set(STUDIO_STATIC_ROUTE_PAGE_IDS).size).toBe(STUDIO_STATIC_ROUTE_PAGE_IDS.length);
  });
});
