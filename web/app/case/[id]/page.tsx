import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CaseScreen } from "@/components/screens/CaseScreen";

export const metadata: Metadata = { title: "Case" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const caseId = Number(id);
  if (!Number.isInteger(caseId) || caseId <= 0) notFound();
  return <CaseScreen key={caseId} caseId={caseId} />;
}
