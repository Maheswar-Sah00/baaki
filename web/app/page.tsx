import type { Metadata } from "next";
import { Features, FairTeaser, FinalCta, GnaniTech, Hero, HowItWorks, Problem, Showcase, SiteFooter, SiteHeader, Trust } from "@/components/site/Site";
import "./site.css";

export const metadata: Metadata = {
  title: { absolute: "Baaki · బాకీ · Say what you’re owed" },
  description:
    "Baaki is a voice app for Hyderabad’s domestic workers. Speak in Telugu or Hinglish; Baaki adds up unpaid wages and sends the employer a polite voice note in their language.",
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
