import type { Metadata } from "next";
import { ConsentScreen } from "@/components/features/consent/ConsentScreen";

export const metadata: Metadata = { title: "Voice consent" };

// /voice/consent?worker=<id>&lang=te-IN|hi-en|en : she repeats the consent sentence; that recording is
// both her consent and her voice sample (G13).
export default function Page() {
  return <ConsentScreen />;
}
