"use client";

/** Restore vertical scroll after scope/query updates that remount tall tables or sync the URL. */
export function scheduleDashboardViewportScrollRestore(scrollY: number): void {
  if (typeof window === "undefined") {
    return;
  }
  const top = scrollY;
  const restore = () => {
    window.scrollTo({ top, left: 0, behavior: "auto" });
  };
  queueMicrotask(restore);
  requestAnimationFrame(restore);
  requestAnimationFrame(() => {
    requestAnimationFrame(restore);
  });
}
