import type { Metadata } from "next";
import { RecipeScreen } from "@/components/screens/RecipeScreen";
import "./r.css";

// Neutral quick-exit page: its tab title and content must not mention Baaki.
export const metadata: Metadata = {
  title: { absolute: "Tomato Pappu Recipe" },
  description: "An easy Andhra-style tomato dal.",
  robots: { index: false, follow: false },
  // Replace the site-wide Baaki preview (child openGraph/twitter objects replace the parent's).
  openGraph: { type: "article", title: "Tomato Pappu Recipe", description: "An easy Andhra-style tomato dal." },
  twitter: { card: "summary", title: "Tomato Pappu Recipe", description: "An easy Andhra-style tomato dal." },
  applicationName: null,
  appleWebApp: null,
};

export default function Page() {
  return <RecipeScreen />;
}
