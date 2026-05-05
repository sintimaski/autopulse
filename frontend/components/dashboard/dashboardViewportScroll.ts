"use client";

/**
 * When scope changes, `router.replace(..., { scroll: false })` can still leave `window.scrollY` at 0
 * for a tick before layout settles. URL-sync effects may then call restore(0) and wipe a good target.
 * Call `pinDashboardViewportScroll` synchronously from handlers that capture scroll at gesture time.
 */
let pinnedScrollTop: number | null = null;
/** Browser timer id (`window.setTimeout`); avoid `ReturnType<typeof setTimeout>` (Node vs DOM mismatch). */
let pinClearTimer: number | null = null;
/**
 * URL-sync can be deferred by debounce + React scheduling; keep the captured viewport long
 * enough for follow-up `router.replace` effects to still restore the original position.
 */
const PIN_MS = 1500;

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

const ANCHOR_SELECTOR = "[data-ap-dashboard-scope-anchor]";

/**
 * After rolling-window or fetch changes, layout can move the main evidence table while the focused
 * scope control stays in view — keep the anchor element at the same viewport offset as before.
 * `anchorViewportTopBefore` must be `getBoundingClientRect().top` from before the scope update.
 */
export function scheduleDashboardScopeAnchorRepair(anchorViewportTopBefore: number): void {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return;
  }
  if (!Number.isFinite(anchorViewportTopBefore)) {
    return;
  }
  const targetTop = anchorViewportTopBefore;
  const run = () => {
    const el = document.querySelector(ANCHOR_SELECTOR);
    if (!(el instanceof Element)) {
      return;
    }
    const now = el.getBoundingClientRect().top;
    const delta = targetTop - now;
    if (Math.abs(delta) > 0.5) {
      window.scrollBy({ left: 0, top: delta, behavior: "auto" });
    }
  };
  queueMicrotask(run);
  requestAnimationFrame(run);
  requestAnimationFrame(() => {
    requestAnimationFrame(run);
  });
  window.setTimeout(run, 0);
  window.setTimeout(run, 48);
  window.setTimeout(run, 120);
  window.setTimeout(run, 240);
  window.setTimeout(run, 400);
}
