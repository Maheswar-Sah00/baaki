import type { MetadataRoute } from "next";
import { DEFAULT_PALETTE } from "@/lib/theme-config";

// Web app manifest (served at /manifest.webmanifest). Colours follow DEFAULT_PALETTE; keep them in
// sync with --meta-bg in app/theme-pale.css / app/theme.css. The splash screen uses background_color
// with the 512 icon (ink tile), so the pale paper background frames it calmly.
const COLORS = {
  pale: { background: "#fbfaf7", theme: "#fbfaf7" },
  warm: { background: "#fcf7f2", theme: "#f2762e" },
  gnani: { background: "#fcf7f2", theme: "#fcf7f2" },
} as const;

const ICON = [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }];

export default function manifest(): MetadataRoute.Manifest {
  const c = COLORS[DEFAULT_PALETTE] ?? COLORS.pale;
  return {
    id: "/app",
    name: "Baaki · బాకీ",
    short_name: "Baaki",
    description: "Say what you are owed, in Telugu or Hinglish. Baaki works out the money still owed and writes to your employer.",
    start_url: "/app",
    scope: "/",
    display: "standalone",
    display_override: ["standalone", "minimal-ui"],
    orientation: "portrait",
    background_color: c.background,
    theme_color: c.theme,
    lang: "en-IN",
    dir: "ltr",
    categories: ["productivity", "finance", "utilities"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
      { src: "/icons/favicon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
    // Long-press the home-screen icon (Android): straight into the three things she needs most.
    shortcuts: [
      { name: "Tell Baaki", short_name: "Speak", description: "Say what you are owed", url: "/speak", icons: ICON },
      { name: "Dues and promises", short_name: "Dues", description: "What each home still owes", url: "/dues", icons: ICON },
      { name: "Help and safety", short_name: "Help", description: "Helplines and the quick exit", url: "/safety", icons: ICON },
    ],
  };
}
