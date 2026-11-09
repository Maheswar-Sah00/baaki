import type { Metadata } from "next";
import { FairOrNot } from "@/components/features/quiz/FairOrNot";

const TITLE = "Fair or Not? Five myths about paying house help";
const DESCRIPTION =
  "A 40-second quiz for employers in Hyderabad: what the Code on Wages, 2019 and Telangana's G.O.Ms.No.6 say about pay day, cuts, advances and the minimum wage. General information, not legal advice.";

export const metadata: Metadata = {
  title: { absolute: `${TITLE} · Baaki` },
  description: DESCRIPTION,
  alternates: { canonical: "/quiz" },
  openGraph: {
    type: "website",
    url: "/quiz",
    siteName: "Baaki",
    title: TITLE,
    description: DESCRIPTION,
    locale: "en_IN",
    images: [{ url: "/icons/icon-512.png", width: 512, height: 512, alt: "Baaki" }],
  },
  twitter: { card: "summary", title: TITLE, description: DESCRIPTION, images: ["/icons/icon-512.png"] },
};

export default function Page() {
  return <FairOrNot />;
}
