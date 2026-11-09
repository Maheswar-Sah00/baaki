import type { Metadata, Viewport } from "next";
import { Noto_Sans, Noto_Sans_Devanagari, Noto_Sans_Telugu } from "next/font/google";
import "./globals.css";

const notoSans = Noto_Sans({ variable: "--font-noto-sans", subsets: ["latin", "latin-ext"], display: "swap" });
const notoTelugu = Noto_Sans_Telugu({
  variable: "--font-noto-telugu",
  subsets: ["telugu"],
  display: "swap",
  preload: false,
});
const notoDevanagari = Noto_Sans_Devanagari({
  variable: "--font-noto-devanagari",
  subsets: ["devanagari"],
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: { default: "Baaki", template: "%s · Baaki" },
  description: "Say what you are owed, in Telugu or Hinglish. Baaki works out the money still owed and writes to your employer.",
  applicationName: "Baaki",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Baaki", statusBarStyle: "black-translucent" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: "#17110d",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${notoSans.variable} ${notoTelugu.variable} ${notoDevanagari.variable}`}>
      <body>{children}</body>
    </html>
  );
}
