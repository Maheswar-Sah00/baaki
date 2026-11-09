import type { Metadata } from "next";
import { EmployerScreen } from "@/components/screens/EmployerScreen";

export const metadata: Metadata = { title: "Payment due", robots: { index: false, follow: false } };

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <EmployerScreen key={token} token={token} />;
}
