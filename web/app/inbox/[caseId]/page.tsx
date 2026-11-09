import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { InboxScreen } from "@/components/features/inbox/InboxScreen";

export const metadata: Metadata = { title: "WhatsApp replies" };

// Share to Baaki + Promise Keeper. `?as_of=YYYY-MM-DD` shifts "today" (demo: "a week later").
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string }>;
  searchParams: Promise<{ as_of?: string | string[]; shared?: string | string[] }>;
}) {
  const { caseId } = await params;
  const id = Number(caseId);
  if (!Number.isInteger(id) || id <= 0) notFound();
  const sp = await searchParams;
  const raw = Array.isArray(sp.as_of) ? sp.as_of[0] : sp.as_of;
  const asOf = raw && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
  const shared = sp.shared === "1";
  return <InboxScreen key={`${id}-${asOf ?? ""}`} caseId={id} asOf={asOf} shared={shared} />;
}
