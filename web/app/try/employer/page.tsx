import type { Metadata } from "next";

import { SandboxDemo } from "@/components/features/sandbox/SandboxDemo";

const TITLE = "Be Sharma ji";
const DESCRIPTION =
  "Be the employer for a minute: hear Lakshmi's polite voice note, check what is owed, and pay. A synthetic demo: Lakshmi is fictional and no money moves.";

export const metadata: Metadata = {
  title: { absolute: `${TITLE} · Baaki` },
  description: DESCRIPTION,
  alternates: { canonical: "/try/employer" },
  openGraph: { type: "website", url: "/try/employer", siteName: "Baaki", title: TITLE, description: DESCRIPTION, locale: "en_IN" },
  robots: { index: false },
};

export default function Page() {
  return <SandboxDemo />;
}
