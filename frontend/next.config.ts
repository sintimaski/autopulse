import type { NextConfig } from "next";

const frontendMode = process.env.AUTOPULSE_FRONTEND_MODE?.trim().toLowerCase() ?? "static";

const nextConfig: NextConfig =
  frontendMode === "sidecar"
    ? {}
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
