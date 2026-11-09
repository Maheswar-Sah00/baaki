import type { Metadata } from "next";
import { FairPayCheck } from "@/components/features/check/FairPayCheck";

const TITLE = "Am I paying my house help fairly?";
const DESCRIPTION =
  "A 30-second check against Telangana's minimum wage (G.O.Ms.No.6, Hyderabad). Four taps, the government source, and nothing you enter is saved.";
const SITE = process.env.NEXT_PUBLIC_SITE_URL;

export const metadata: Metadata = {
  title: { absolute: `${TITLE} · Baaki` },
  description: DESCRIPTION,
  ...(SITE ? { metadataBase: new URL(SITE) } : {}),
  alternates: { canonical: "/check" },
  openGraph: {
    type: "website",
    url: "/check",
    siteName: "Baaki",
    title: TITLE,
    description: DESCRIPTION,
    locale: "en_IN",
    images: [{ url: "/icons/icon-512.png", width: 512, height: 512, alt: "Baaki" }],
  },
  twitter: { card: "summary", title: TITLE, description: DESCRIPTION, images: ["/icons/icon-512.png"] },
};

export default function Page() {
  return <FairPayCheck />;
}
