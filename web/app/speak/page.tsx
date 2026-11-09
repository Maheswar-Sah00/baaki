import type { Metadata } from "next";
import { SpeakScreen } from "@/components/screens/SpeakScreen";

export const metadata: Metadata = { title: "Speak" };

export default function Page() {
  return <SpeakScreen />;
}
