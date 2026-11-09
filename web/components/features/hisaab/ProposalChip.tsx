"use client";

// One proposed correction: "−₹2,000 · cash · October", labelled "said by the employer", with its state.
import type { HisaabProposal } from "@/lib/features/hisaab";
import s from "./hisaab.module.css";

export function ProposalChip({ p, side }: { p: HisaabProposal; side: "employer" | "worker" }) {
  return (
    <div className={s.row} data-hisaab-id={p.id}>
      <span className={s.chip}>
        <span className={s.chipMain}>{p.chip.main}</span>
        <span className={s.saidBy}>{p.said_by_label}</span>
      </span>
      <span className={`${s.state} ${s[p.display_state]}`}>
        {side === "employer" ? p.status_text_employer : p.status_text_worker}
      </span>
    </div>
  );
}
