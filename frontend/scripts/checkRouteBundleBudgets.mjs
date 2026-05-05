import { readFileSync } from "node:fs";
import path from "node:path";

const diagnosticsPath = path.resolve(".next/diagnostics/route-bundle-stats.json");
const stats = JSON.parse(readFileSync(diagnosticsPath, "utf8"));

const routeBudgets = {
  "/dashboard": 975_000,
  "/widgets-showcase": 925_000,
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
