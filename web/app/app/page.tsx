import type { Metadata } from "next";
import { HomeScreen } from "@/components/screens/HomeScreen";

export const metadata: Metadata = { title: "My homes" };

// The worker app home. The marketing website lives at "/".
export default function Page() {
  return <HomeScreen />;
}
