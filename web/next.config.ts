import path from "node:path";
import type { NextConfig } from "next";

// FastAPI backend. The phone only ever talks to this Next origin (through an HTTPS tunnel
// in demos); /api/* is proxied here so API keys stay on the server.
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// Tunnel hostnames allowed to load dev-only assets from `next dev`.
// Add more with EXTRA_DEV_ORIGINS="my.host.dev,*.other.dev".
const DEV_ORIGINS = [
  "*.trycloudflare.com",
  "*.ngrok-free.app",
  "*.ngrok-free.dev",
  "*.ngrok.app",
  "*.loca.lt",
  "**.devtunnels.ms",
  ...(process.env.EXTRA_DEV_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
];

// Pin the project root to web/ (lockfiles in parent folders are ignored).
const PROJECT_ROOT = path.join(__dirname);

const nextConfig: NextConfig = {
  // The demo runner builds into its own folder (NEXT_DIST_DIR=.next-demo) so other builds can't
  // overwrite the app that is being filmed.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  outputFileTracingRoot: PROJECT_ROOT,
  poweredByHeader: false,
  allowedDevOrigins: DEV_ORIGINS,
  experimental: {
    // STT on a long voice note can take a while; the default proxy timeout is 30 s.
    proxyTimeout: 180_000,
  },
  turbopack: {
    root: PROJECT_ROOT,
    rules: {
      // Only the global stylesheet needs Tailwind; matching "*.css" broke CSS modules
      // (x.module.css was renamed to x.module.css.css and lost its class exports).
      "globals.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  async headers() {
    return [
      {
        // Security headers on every page (GAP_AUDIT #30). The mic is used by this origin only.
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=()" },
        ],
      },
      {
        source: "/manifest.webmanifest",
        headers: [
          { key: "Content-Type", value: "application/manifest+json; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache" },
        ],
      },
      {
        // The service worker must never be served stale, or updates would not reach phones.
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
    ];
  },
};

export default nextConfig;
