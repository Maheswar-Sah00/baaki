"use client";

// One line of the running account: what (kind · month, or "Paid · UPI" for his "I've paid" claim), who said it and
// when, its state in the reader's language, and the signed amount ("−₹2,000"). A disputed line is struck through.
import type { HisaabProposal } from "@/lib/features/hisaab";
import type { UiLang } from "@/lib/i18n";
import { monthLabel, shortDate } from "@/lib/format";
import { CheckIcon, ClockIcon, CrossIcon } from "@/components/ui/icons";
import { KIND_LABEL, workerStrings } from "./strings";
import s from "./hisaab.module.css";

/** Label for a proposal. Payment claims carry kind "said_paid", so check `type` first and use their method. */
export function whatOf(p: HisaabProposal, lang: UiLang): string {
  const labels = KIND_LABEL[lang] ?? KIND_LABEL.en;
  if (p.type === "payment_claim") {
    const via = p.method ? labels[p.method] ?? p.method : "";
    return workerStrings(lang).paidVia(via || "·").replace(/ · ·$/, "");
  }
  return [labels[p.kind] ?? p.kind, p.month ? monthLabel(p.month, lang) : null].filter(Boolean).join(" · ");
}

export function ProposalChip({ p, side, lang = "en" }: { p: HisaabProposal; side: "employer" | "worker"; lang?: UiLang }) {
  const state = p.display_state;
  const when = shortDate(p.decided_at ?? p.created_at, lang);
  const who = side === "worker" ? workerStrings(lang).saidBy(p.said_by_name) : null;
  return (
    <div className={s.entry} data-state={state} data-type={p.type} data-hisaab-id={p.id}>
      <span className={s.entryIcon} aria-hidden="true">
        {state === "accepted" ? <CheckIcon /> : state === "disputed" ? <CrossIcon /> : <ClockIcon />}
      </span>
      <span className={s.entryMain}>
        <span className={s.entryTitle}>{whatOf(p, lang)}</span>
        <span className={s.entrySub}>{[who, when].filter(Boolean).join(" · ")}</span>
        <span className={s.entryState}>{side === "employer" ? p.status_text_employer : p.status_text_worker}</span>
      </span>
      <span className={s.entryAmt}>{p.type === "payment_claim" ? p.amount_display : p.signed_display}</span>
    </div>
  );
}
