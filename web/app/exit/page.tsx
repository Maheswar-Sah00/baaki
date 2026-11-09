import type { Metadata } from "next";
import { ExitKitScreen } from "@/components/features/exit/ExitKitScreen";

export const metadata: Metadata = { title: "Asked to leave" };

function id(v: string | string[] | undefined): number | null {
  const n = Number(Array.isArray(v) ? v[0] : v);
  return Number.isInteger(n) && n > 0 ? n : null;
}

// /exit?employer=<id>&case=<id>: the Exit Kit for one home.
export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const q = await searchParams;
  const employerId = id(q.employer);
  const caseId = id(q.case);
  return <ExitKitScreen key={`${employerId}-${caseId}`} employerId={employerId} caseId={caseId} />;
}
