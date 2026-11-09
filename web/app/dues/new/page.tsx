import type { Metadata } from "next";
import { NewDuesScreen } from "@/components/features/dues/NewDuesScreen";

export const metadata: Metadata = { title: "Who owes you?" };

// Pick a kind (?kind=vendor|chit|other skips the tiles), then speak or type what is owed.
export default async function Page({ searchParams }: { searchParams: Promise<{ kind?: string | string[] }> }) {
  const sp = await searchParams;
  const raw = Array.isArray(sp.kind) ? sp.kind[0] : sp.kind;
  const kind = raw === "vendor" || raw === "chit" || raw === "other" ? raw : null;
  return <NewDuesScreen initialKind={kind} />;
}
