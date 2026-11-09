import type { Metadata } from "next";
import { SharePicker } from "@/components/features/inbox/SharePicker";

export const metadata: Metadata = { title: "Share to Baaki" };

// Landing page of the PWA share target (add-on): pick which home the shared WhatsApp reply is from.
export default function Page() {
  return <SharePicker />;
}
