// Display helpers. Money is always shown as Indian-grouped rupees; estimates keep paise.

const INR0 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const INR2 = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** ₹12,692 (paise shown only when present). */
export function inr(amount: number | null | undefined): string {
  if (amount == null || !Number.isFinite(amount)) return "₹0";
  const whole = Math.abs(amount - Math.round(amount)) < 0.005;
  return `₹${whole ? INR0.format(Math.round(amount)) : INR2.format(amount)}`;
}

/** Whole rupees for animated counters. */
export function inrWhole(amount: number): string {
  return `₹${INR0.format(Math.round(amount))}`;
}

const LOCALE: Record<string, string> = { te: "te-IN", "hi-en": "hi-IN", en: "en-IN" };

/** 9 Nov 2026 in the reader's language. */
export function shortDate(iso: string | null | undefined, uiLang = "en"): string {
  if (!iso) return "";
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(LOCALE[uiLang] ?? "en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function dateTime(iso: string | null | undefined, uiLang = "en"): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(LOCALE[uiLang] ?? "en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** "2026-08" -> "Aug 2026". */
export function monthLabel(ym: string | null | undefined, uiLang = "en"): string {
  if (!ym) return "";
  const d = new Date(`${ym}-01T00:00:00`);
  if (Number.isNaN(d.getTime())) return ym;
  return d.toLocaleDateString(LOCALE[uiLang] ?? "en-IN", { month: "short", year: "numeric" });
}

export function shortHash(h: string | null | undefined): string {
  return h ? `${h.slice(0, 8)}…${h.slice(-4)}` : "";
}

/** Today in IST as YYYY-MM-DD. */
export function todayIst(): string {
  return new Date(Date.now() + 5.5 * 3600_000).toISOString().slice(0, 10);
}

/** Worker-side label for an itemised line: localized kind + month (the backend label is English). */
export function itemLabel(
  t: (key: "item.unpaid_wage" | "item.illegal_deduction" | "item.min_wage_shortfall" | "item.final_settlement" | "item.other") => string,
  item: { kind: string; month: string | null },
  uiLang = "en",
): string {
  const key =
    item.kind === "unpaid_wage" || item.kind === "illegal_deduction" || item.kind === "min_wage_shortfall" || item.kind === "final_settlement"
      ? (`item.${item.kind}` as const)
      : ("item.other" as const);
  const month = monthLabel(item.month, uiLang);
  return month ? `${t(key)} · ${month}` : t(key);
}
