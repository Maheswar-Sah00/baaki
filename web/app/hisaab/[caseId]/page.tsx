import type { Metadata } from "next";
import { HisaabWorker } from "@/components/features/hisaab/HisaabWorker";

export const metadata: Metadata = {
  title: { absolute: "Hisaab Milao · Baaki" },
  robots: { index: false, follow: false },
};

// V09 Hisaab Milao, worker side: hear the employer's correction, accept or reject.
export default async function Page({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <HisaabWorker key={caseId} caseId={caseId} />;
}
