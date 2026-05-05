"use client";

/**
 * When scope changes, `router.replace(..., { scroll: false })` can still leave `window.scrollY` at 0
 * for a tick before layout settles. URL-sync effects may then call restore(0) and wipe a good target.
 * Call `pinDashboardViewportScroll` synchronously from handlers that capture scroll at gesture time.
 */
let pinnedScrollTop: number | null = null;
/** Browser timer id (`window.setTimeout`); avoid `ReturnType<typeof setTimeout>` (Node vs DOM mismatch). */
let pinClearTimer: number | null = null;
const PIN_MS = 220;

export function pinDashboardViewportScroll(scrollY: number): void {
  if (typeof window === "undefined") {
    return;
  }
  pinnedScrollTop = scrollY;
  if (pinClearTimer !== null) {
    window.clearTimeout(pinClearTimer);
  }
  pinClearTimer = window.setTimeout(() => {
    pinnedScrollTop = null;
    pinClearTimer = null;
  }, PIN_MS);
}

/** Restore vertical scroll after scope/query updates that remount tall tables or sync the URL. */
export function scheduleDashboardViewportScrollRestore(scrollY: number): void {
  if (typeof window === "undefined") {
    return;
  }
  const top = pinnedScrollTop !== null ? pinnedScrollTop : scrollY;
  const restore = () => {
    window.scrollTo({ top, left: 0, behavior: "auto" });
  };
  queueMicrotask(restore);
  requestAnimationFrame(restore);
  requestAnimationFrame(() => {
    requestAnimationFrame(restore);
  });
  window.setTimeout(restore, 0);
  window.setTimeout(restore, 48);
  window.setTimeout(restore, 120);
}
