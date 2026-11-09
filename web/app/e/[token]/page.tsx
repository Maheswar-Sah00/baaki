import type { Metadata } from "next";
import { EmployerScreen } from "@/components/screens/EmployerScreen";
import { OG_IMAGE } from "@/lib/site";

// WhatsApp/Telegram unfurl this link: the preview must never show the amount, the worker or the employer.
const TITLE = "A message for you via Baaki";
const DESCRIPTION = "Open to listen to a short voice note and see the details.";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  robots: { index: false, follow: false },
  referrer: "no-referrer",
  openGraph: { type: "website", siteName: "Baaki", title: TITLE, description: DESCRIPTION, images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: [OG_IMAGE.url] },
};

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <EmployerScreen key={token} token={token} />;
}
