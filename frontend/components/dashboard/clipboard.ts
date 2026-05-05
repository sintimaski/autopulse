"use client";

import { stripDashboardBookmarkLocationSearch } from "./dashboardQueryState";

export async function copyTextToClipboard(value: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through to legacy copy path.
    }
  }

  if (typeof document === "undefined") {
    return false;
  }

  try {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "true");
    area.style.position = "fixed";
    area.style.opacity = "0";
    area.style.pointerEvents = "none";
    document.body.appendChild(area);
    area.focus();
    area.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(area);
    return copied;
  } catch {
    return false;
  }
}

export function buildBookmarkUrl(fragment: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const nextHash = fragment.startsWith("#") ? fragment : `#${fragment}`;
  const search = stripDashboardBookmarkLocationSearch(window.location.search);
  return `${window.location.origin}${window.location.pathname}${search}${nextHash}`;
}
