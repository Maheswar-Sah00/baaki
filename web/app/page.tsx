import type { Metadata } from "next";
import { Faq, Features, FinalCta, Hero, HowItWorks, Interfaces, Problem, ProofBand, SiteFooter, SiteHeader, Trust } from "@/components/site/Site";
import { SITE_SLOTS, existingAssets } from "@/components/site/assets";
import { OG_IMAGE } from "@/lib/site";
import "./site.css";

const TITLE = "Baaki · బాకీ · A wage advocate in her pocket";
const DESCRIPTION =
  "81% of Hyderabad’s domestic workers earn below the minimum wage. Baaki knows the law, does the maths, asks the employer for her and keeps the proof. She just speaks.";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: { type: "website", url: "/", siteName: "Baaki", title: TITLE, description: DESCRIPTION, locale: "en_IN", images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: [OG_IMAGE.url] },
};

// Marketing website. The worker app lives at /app.
export default function Home() {
  const art = existingAssets(SITE_SLOTS);
  return (
    <div className="site site-home">
      <SiteHeader />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <Features photos={art} />
        <Interfaces art={art} />
        <ProofBand art={art} />
        <Trust />
        <Faq />
        <FinalCta art={art} />
      </main>
      <SiteFooter />
    </div>
  );
}
