import type { Metadata } from "next";
import { HisaabEmployer } from "@/components/features/hisaab/HisaabEmployer";

export const metadata: Metadata = {
  title: { absolute: "Something's different? · Baaki" },
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

// V09 Hisaab Milao, employer side (same token as the employer page /e/{token}).
export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <HisaabEmployer key={token} token={token} />;
}
