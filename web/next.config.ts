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

// Pin the project root to web/ (B:\Projects holds unrelated lockfiles).
const PROJECT_ROOT = path.join(__dirname);

const nextConfig: NextConfig = {
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
      "*.css": {
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
