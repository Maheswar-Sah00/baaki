import type { Metadata } from "next";
import { SiteFooter } from "@/components/site/Site";
import { ProofHeader } from "@/components/features/proof/ProofHeader";
import { ProofView } from "@/components/features/proof/ProofView";
import "../site.css";
import "@/components/features/proof/proof.css";

const TITLE = "Noise proof";
const DESCRIPTION =
  "Every rupee amount Baaki heard in a noisy kitchen, on an 8 kHz phone line and through WhatsApp compression, with every clip playable and the misses shown.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/proof" },
  openGraph: {
    type: "website",
    url: "/proof",
    siteName: "Baaki",
    title: `${TITLE} · Baaki`,
    description: DESCRIPTION,
    locale: "en_IN",
    images: [{ url: "/og/proof-og.png", width: 1200, height: 630, alt: "Baaki noise proof: rupee amounts heard exactly" }],
  },
  twitter: { card: "summary_large_image", title: `${TITLE} · Baaki`, description: DESCRIPTION, images: ["/og/proof-og.png"] },
};

// Public proof page (G04+V14): results of backend/scripts/bench_noisy.py, served by GET /api/proof.
// site.css is loaded for the shared footer; the page itself is styled by proof.css (pf-*).
export default function ProofPage() {
  return (
    <div className="site pf-site">
      <ProofHeader />
      <main>
        <ProofView />
      </main>
      <SiteFooter />
    </div>
  );
}
