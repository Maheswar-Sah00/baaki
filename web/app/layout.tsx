import type { Metadata, Viewport } from "next";
import { Instrument_Serif, Inter, Noto_Sans_Devanagari, Noto_Sans_Telugu } from "next/font/google";
import localFont from "next/font/local";
import { THEME_INIT_SCRIPT } from "@/lib/theme-config";
import { OG_IMAGE, SITE_URL } from "@/lib/site";
import { ServiceWorkerRegister } from "@/components/pwa/ServiceWorkerRegister";
import "./theme.css";
import "./theme-pale.css";
import "./globals.css";
import "./screens.css";

// Display serif in the spirit of Gnani's Gambarino (not on Google Fonts) + Inter for UI text,
// with Noto Sans Telugu / Devanagari for Indic script. Tokens: --font-display, --font-sans.
// Cabinet Grotesk (Fontshare, free for commercial use), self-hosted: the headline face (as on usevyra.com).
const cabinet = localFont({ src: "./fonts/CabinetGrotesk-Variable.woff2", variable: "--font-cabinet", weight: "100 900", display: "swap" });
const serif = Instrument_Serif({ variable: "--font-serif", subsets: ["latin", "latin-ext"], weight: "400", style: ["normal", "italic"], display: "swap" });
const inter = Inter({ variable: "--font-inter", subsets: ["latin", "latin-ext"], display: "swap" });
const notoTelugu = Noto_Sans_Telugu({ variable: "--font-noto-telugu", subsets: ["telugu"], display: "swap", preload: false });
const notoDevanagari = Noto_Sans_Devanagari({ variable: "--font-noto-devanagari", subsets: ["devanagari"], display: "swap", preload: false });

const DESCRIPTION = "Say what you are owed, in Telugu or Hinglish. Baaki works out the money still owed and writes to your employer.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Baaki · బాకీ", template: "%s · Baaki" },
  description: DESCRIPTION,
  // Site-wide link preview: generic on purpose. Pages override it (/e/{token} with its own generic card,
  // /r with a neutral one); child openGraph/twitter objects replace these, they do not merge.
  openGraph: {
    type: "website",
    siteName: "Baaki",
    title: "Baaki · బాకీ",
    description: DESCRIPTION,
    locale: "en_IN",
    images: [OG_IMAGE],
  },
  twitter: { card: "summary_large_image", title: "Baaki · బాకీ", description: DESCRIPTION, images: [OG_IMAGE.url] },
  applicationName: "Baaki",
  appleWebApp: { capable: true, title: "Baaki", statusBarStyle: "default" },
  formatDetection: { telephone: false },
  icons: {
    icon: [
      { url: "/icons/favicon.svg", type: "image/svg+xml" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
};

export const viewport: Viewport = {
  // Overwritten before paint by THEME_INIT_SCRIPT with the active theme's --meta-bg.
  themeColor: "#fbfaf7",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en-IN"
      suppressHydrationWarning
      className={`${cabinet.variable} ${serif.variable} ${inter.variable} ${notoTelugu.variable} ${notoDevanagari.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        {children}
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}
