import type { MetadataRoute } from "next";
import { DEFAULT_PALETTE } from "@/lib/theme-config";

// Web app manifest (served at /manifest.webmanifest). Colours follow DEFAULT_PALETTE; keep them in
// sync with --meta-bg / --accent in app/theme.css.
const COLORS = {
  warm: { background: "#fcf7f2", theme: "#f2762e" },
  gnani: { background: "#fcf7f2", theme: "#fcf7f2" },
} as const;

export default function manifest(): MetadataRoute.Manifest {
  const c = COLORS[DEFAULT_PALETTE];
  return {
    id: "/app",
    name: "Baaki · బాకీ",
    short_name: "Baaki",
    description: "Say what you are owed, in Telugu or Hinglish. Baaki works out the money still owed and writes to your employer.",
    start_url: "/app",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: c.background,
    theme_color: c.theme,
    lang: "en-IN",
    categories: ["productivity", "finance", "utilities"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Tell Baaki", short_name: "Speak", url: "/speak", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Help", short_name: "Help", url: "/safety", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}
