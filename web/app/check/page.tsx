import type { Metadata } from "next";
import { FairPayCheck } from "@/components/features/check/FairPayCheck";
import { SiteFooter } from "@/components/site/Site";
import { existingAssets } from "@/components/site/assets";
import "../site.css";

const TITLE = "Am I paying my house help fairly?";
const DESCRIPTION =
  "A 30-second check against Telangana's minimum wage (G.O.Ms.No.6, Hyderabad). Four taps, the government source, and nothing you enter is saved.";

export const metadata: Metadata = {
  title: { absolute: `${TITLE} · Baaki` },
  description: DESCRIPTION,
  alternates: { canonical: "/check" },
  openGraph: {
    type: "website",
    url: "/check",
    siteName: "Baaki",
    title: TITLE,
    description: DESCRIPTION,
    locale: "en_IN",
    images: [{ url: "/og/check-og.png", width: 1200, height: 630, alt: "Am I paying my house help fairly? Baaki Fair Pay Check" }],
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: ["/og/check-og.png"] },
};

// The photo slot renders only once its file exists (checked here, on the server), so a missing photo
// never 404s in the browser. The shared site footer closes the page (site.css styles it).
export default function Page() {
  return (
    <>
      <FairPayCheck photo={existingAssets(["check-payday-envelope"]).length > 0} />
      <div className="site fc-site-foot">
        <SiteFooter />
      </div>
    </>
  );
}
