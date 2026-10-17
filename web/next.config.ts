import type { NextConfig } from "next";

// FastAPI backend (uv run vrag api). /api and /media are proxied so the browser sees one origin.
const BACKEND = process.env.VRAG_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Let the dev server be opened from other machines on the LAN / tailnet: comma-separated hosts in
  // VRAG_DEV_ORIGINS (e.g. in web/.env.local). Wildcards match a single subdomain level only, so a
  // full MagicDNS name needs its own entry.
  allowedDevOrigins: (process.env.VRAG_DEV_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Generation over several video clips can take a while.
  experimental: { proxyTimeout: 300_000, proxyClientMaxBodySize: "65mb" },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/media/:path*", destination: `${BACKEND}/media/:path*` },
      { source: "/health", destination: `${BACKEND}/api/health` },
      { source: "/api-docs", destination: `${BACKEND}/docs` },
      { source: "/openapi.json", destination: `${BACKEND}/openapi.json` },
    ];
  },
};

export default nextConfig;
