import type { Metadata } from "next";
import { SafetyScreen } from "@/components/screens/SafetyScreen";

export const metadata: Metadata = { title: "Help" };

export default function Page() {
  return <SafetyScreen />;
}
