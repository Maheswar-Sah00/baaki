import type { Metadata } from "next";
import { Features, FairTeaser, FinalCta, GnaniTech, Hero, HowItWorks, Problem, Showcase, SiteFooter, SiteHeader, Trust } from "@/components/site/Site";
import { OG_IMAGE } from "@/lib/site";
import "./site.css";

const TITLE = "Baaki · బాకీ · A wage advocate in her pocket";
const DESCRIPTION =
  "81% of Hyderabad’s domestic workers are paid below the legal minimum. Baaki knows the law, does the maths, asks the employer for her and keeps the proof. She just speaks.";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: { type: "website", url: "/", siteName: "Baaki", title: TITLE, description: DESCRIPTION, locale: "en_IN", images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: [OG_IMAGE.url] },
};

// Marketing website. The worker app lives at /app.
export default function Home() {
  return (
    <div className="site">
      <SiteHeader />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <Showcase />
        <Features />
        <FairTeaser />
        <GnaniTech />
        <Trust />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  );
}
