import type { Metadata } from "next";
import { ConfirmScreen } from "@/components/screens/ConfirmScreen";

export const metadata: Metadata = { title: "Confirm" };

export default function Page() {
  return <ConfirmScreen />;
}
