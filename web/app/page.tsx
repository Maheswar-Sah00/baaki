import type { Metadata } from "next";
import { Features, FairTeaser, FinalCta, GnaniTech, Hero, HowItWorks, Problem, Showcase, SiteFooter, SiteHeader, Trust } from "@/components/site/Site";
import { OG_IMAGE } from "@/lib/site";
import "./site.css";

const TITLE = "Baaki · బాకీ · Say what you’re owed";
const DESCRIPTION =
  "Baaki is a voice app for Hyderabad’s domestic workers. Speak in Telugu or Hinglish; Baaki adds up unpaid wages and sends the employer a polite voice note in their language.";

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
