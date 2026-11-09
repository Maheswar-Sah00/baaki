import type { Metadata } from "next";
import { VoiceScreen } from "@/components/screens/VoiceScreen";

export const metadata: Metadata = { title: "My voice" };

export default function Page() {
  return <VoiceScreen />;
}
