import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StoryReplay } from "@/components/features/story/StoryReplay";

export const metadata: Metadata = { title: "Case replay", robots: { index: false, follow: false } };

// V12 Case Replay: private like the other worker pages (needs the case id; no listing anywhere).
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id: raw } = await params;
  const id = Number(raw);
  if (!Number.isInteger(id) || id <= 0) notFound();
  return <StoryReplay key={id} caseId={id} />;
}
