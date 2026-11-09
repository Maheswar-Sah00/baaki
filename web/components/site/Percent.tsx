"use client";

// Count-up numbers for the website (client wrappers: a server component cannot pass `format`).
import { CountUp } from "@/components/ui/kit";

const pct = (n: number) => `${n}%`;
const lakh = (n: number) => `${n} lakh`;

export function Percent({ value }: { value: number }) {
  return <CountUp value={value} format={pct} durationMs={1600} />;
}

export function Lakh({ value }: { value: number }) {
  return <CountUp value={value} format={lakh} durationMs={1200} />;
}
