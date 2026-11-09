import type { Metadata } from "next";
import { RecipeScreen } from "@/components/screens/RecipeScreen";

// Neutral quick-exit page: its tab title and content must not mention Baaki.
export const metadata: Metadata = {
  title: { absolute: "Tomato Pappu Recipe" },
  description: "An easy Andhra-style tomato dal.",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <RecipeScreen />;
}
