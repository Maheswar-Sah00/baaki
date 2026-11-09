import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DuesDetailScreen } from "@/components/features/dues/DuesDetailScreen";

export const metadata: Metadata = { title: "Promises" };

// One person who owes you: chips, promise timeline, reminder, record pack. `?as_of=YYYY-MM-DD` = demo time travel.
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ as_of?: string | string[] }>;
}) {
  const { id } = await params;
  const n = Number(id);
  if (!Number.isInteger(n) || n <= 0) notFound();
  const sp = await searchParams;
  const raw = Array.isArray(sp.as_of) ? sp.as_of[0] : sp.as_of;
  const asOf = raw && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
  return <DuesDetailScreen key={`${n}-${asOf ?? ""}`} id={n} asOf={asOf} />;
}
