import type { Metadata } from "next";
import { SiteFooter } from "@/components/site/Site";
import { ProofHeader } from "@/components/features/proof/ProofHeader";
import { ProofView } from "@/components/features/proof/ProofView";
import "../site.css";
import "@/components/features/proof/proof.css";

export const metadata: Metadata = {
  title: "Noise proof",
  description:
    "Every rupee amount Baaki heard in a noisy kitchen, on an 8 kHz phone line and through WhatsApp compression, with every clip playable and the misses shown.",
};

// Public proof page (G04+V14): results of backend/scripts/bench_noisy.py, served by GET /api/proof.
export default function ProofPage() {
  return (
    <div className="site">
      <ProofHeader />
      <main>
        <ProofView />
      </main>
      <SiteFooter />
    </div>
  );
}
