import type { Metadata } from "next";
import { DuesListScreen } from "@/components/features/dues/DuesListScreen";

export const metadata: Metadata = { title: "People who owe you" };

// Baaki for every promise: everyone who owes the user, by kind. `?as_of=YYYY-MM-DD` shifts "today" (demo).
export default async function Page({ searchParams }: { searchParams: Promise<{ as_of?: string | string[] }> }) {
  const sp = await searchParams;
  const raw = Array.isArray(sp.as_of) ? sp.as_of[0] : sp.as_of;
  const asOf = raw && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
  return <DuesListScreen key={asOf ?? ""} asOf={asOf} />;
}
