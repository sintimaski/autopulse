import type { NextConfig } from "next";

const frontendMode = process.env.AUTOPULSE_FRONTEND_MODE?.trim().toLowerCase() ?? "static";

/** Hostnames (no scheme/port) allowed to load Next dev internals (e.g. `/_next/webpack-hmr`) from a LAN URL. */
function parseAllowedDevOrigins(): string[] {
  const raw = process.env.AUTOPULSE_NEXT_ALLOWED_DEV_ORIGINS?.trim();
  if (!raw) return [];
  const parts = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((host) => host.replace(/^https?:\/\//i, "").split("/")[0] ?? "")
    .filter(Boolean);
  return [...new Set(parts)];
}

const allowedDevOrigins = parseAllowedDevOrigins();

const nextConfig: NextConfig =
  frontendMode === "sidecar"
    ? {
        // Baked into the client bundle so ``buildApiUrl`` can fix relative ``/autopulse`` when Next runs on :3000.
        env: {
          NEXT_PUBLIC_AUTOPULSE_FRONTEND_MODE: "sidecar",
        },
        ...(allowedDevOrigins.length > 0 ? { allowedDevOrigins } : {}),
      }
    : {
        output: "export",
        basePath: "/autopulse/ui",
        assetPrefix: "/autopulse/ui",
        trailingSlash: true,
        images: {
          unoptimized: true,
        },
      };

export default nextConfig;
