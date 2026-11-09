import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RaiseWorkerScreen } from "@/components/features/raise/RaiseWorkerScreen";

export const metadata: Metadata = { title: "Ask for a raise" };

// Haq Raise, the worker side: her pay vs the legal estimate, a plan, and a warm request in the employer's language.
export default async function Page({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  const id = Number(caseId);
  if (!Number.isInteger(id) || id <= 0) notFound();
  return <RaiseWorkerScreen key={id} caseId={id} />;
}
