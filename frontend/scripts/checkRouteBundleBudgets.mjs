import { readFileSync } from "node:fs";
import path from "node:path";

const diagnosticsPath = path.resolve(".next/diagnostics/route-bundle-stats.json");
const stats = JSON.parse(readFileSync(diagnosticsPath, "utf8"));

const routeBudgets = {
  /**
   * Uncompressed first-load JS (`firstLoadUncompressedJsBytes`); keep a small slack above current dashboard chunk.
   * Raised 1_024_000 -> 1_060_000 for the console design-system refresh: shared `Panel` chrome on every overview
   * chart + panel-vocabulary icons. Header command search is `next/dynamic` so it stays off first-load JS.
   */
  "/dashboard": 1_060_000,
  "/w/[pageId]": 925_000,
};

const formatBytes = (bytes) => `${(bytes / 1024).toFixed(1)} KiB`;

let hasFailure = false;

for (const [route, maxBytes] of Object.entries(routeBudgets)) {
  const routeStat = stats.find((item) => item.route === route);
  if (!routeStat) {
    console.error(`[bundle-budget] Missing route stats for ${route}.`);
    hasFailure = true;
    continue;
  }

  const actualBytes = Number(routeStat.firstLoadUncompressedJsBytes ?? 0);
  const status = actualBytes <= maxBytes ? "PASS" : "FAIL";
  console.log(
    `[bundle-budget] ${status} ${route}: ${formatBytes(actualBytes)} (budget ${formatBytes(maxBytes)})`,
  );

  if (actualBytes > maxBytes) {
    hasFailure = true;
  }
}

if (hasFailure) {
  process.exit(1);
}
