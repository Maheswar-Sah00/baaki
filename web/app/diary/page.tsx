import type { Metadata } from "next";
import { DiaryScreen } from "@/components/screens/DiaryScreen";

export const metadata: Metadata = { title: "Work diary" };

export default function Page() {
  return <DiaryScreen />;
}
