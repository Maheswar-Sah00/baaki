// V09 Hisaab Milao (backend: backend/app/routes/hisaab.py). The employer proposes a correction by voice or typing;
// the worker hears it in her language and accepts or rejects. Every amount and month comes from the backend
// (app.lang parsers); nothing is computed here except display.

import { ApiError, audioUploadName } from "@/lib/api";

/** Correction kinds. A proposal's `kind` can also be "said_paid": the employer's "I've paid" claim (see `type`). */
export type HisaabKind = "cash" | "upi" | "advance" | "other";
export type HisaabStatus = "proposed" | "accepted" | "rejected";

export type HisaabProposal = {
  id: number;
  /** Absent on employer-side responses (the employer never gets the worker's case id). */
  case_id?: number;
  /** "payment_claim" = he says he paid (she confirms the money arrived); "correction" = he remembers it differently. */
  type: "payment_claim" | "correction";
  method?: string;
  /** Sandbox demo claims, confirmed automatically and labelled synthetic. */
  demo?: boolean;
  status: HisaabStatus;
  display_state: "proposed" | "accepted" | "disputed";
  said_by: "employer" | string;
  said_by_name: string;
  said_by_label: string;
  amount: number;
  amount_display: string;
  signed_display: string;
  amount_source: "spoken" | "typed" | string;
  /** Correction kind. For a payment claim (`type === "payment_claim"`) the backend sends "said_paid": check `type`
   *  first, and don't index the correction-kind label tables with it. */
  kind: HisaabKind;
  month: string | null;
  month_label: string | null;
  transcript: string;
  source: "voice" | "text" | string;
  language: string;
  chip: { text: string; main: string; said_by_label: string };
  readback: { text: string; speech: string; language: string; audio_url: string };
  employer_audio_url: string | null;
  exceeds_balance: boolean;
  payment_id: number | null;
  balance_before: number | null;
  balance_after: number | null;
  status_text_employer: string;
  status_text_worker: string;
  created_at: string;
  decided_at: string | null;
};

export type HisaabMoney = {
  total_due: number;
  amount_paid: number;
  balance: number;
  balance_display: string;
  case_status: string;
  /** Paid beyond a (reduced) total; 0 normally. */
  overpaid?: number;
};

export type HisaabSummary = HisaabMoney & {
  case_id: number;
  worker: { name: string; language: string };
  employer: { name: string; language: string };
  proposals: HisaabProposal[];
  pending: number;
  /** Pending "I've paid" claims waiting for her: show "Did the money arrive?". */
  pending_claims: number;
  disputed_total: number;
  notice: string;
};

export type ProposeResult = HisaabMoney & {
  state: "proposed";
  proposal: HisaabProposal;
  readback_audio_error: unknown;
  message: string;
};

export type DecideResult = HisaabMoney & {
  proposal: HisaabProposal;
  decision: "accept" | "reject";
  changed: boolean;
  /** Set when an accept recorded money (ledger Payment row). */
  payment?: {
    payment_id: number;
    recorded: number;
    requested: number;
    /** Claimed beyond what was owed (capped, not recorded). */
    excess: number;
    balance_before: number;
    balance_after: number;
    fully_paid: boolean;
  } | null;
  fully_paid?: boolean;
  /** A paid case went back to open because the total rose. */
  reopened?: boolean;
  badge?: import("@/lib/types").Badge | null;
  /** "Paisa aa gaya" for her phone, only after she confirms a payment claim. */
  alert?: import("@/lib/types").PaidAlert | null;
  plan?: unknown;
  /** Sandbox only: "Demo: Lakshmi confirmed (synthetic)". */
  confirmed_label?: string | null;
};

/** 422 "no_amount": he spoke but no amount was heard. `transcript` lets the page prefill the text box. */
export type NoAmount = { error: "no_amount"; message: string; message_en: string; transcript: string };

async function ok<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let message = `${res.status}`;
  let body: unknown = null;
  let code: string | null = null;
  try {
    body = await res.json();
    const d = (body as { detail?: unknown })?.detail;
    if (typeof d === "string") message = d;
    else if (d && typeof d === "object") {
      const o = d as { message?: string; error?: string };
      if (o.message) message = o.message;
      if (o.error) code = o.error;
    }
  } catch {
    /* keep the status */
  }
  throw new ApiError(message, res.status, body, code);
}

export function noAmountOf(err: unknown): NoAmount | null {
  if (!(err instanceof ApiError) || err.code !== "no_amount") return null;
  return (err.body as { detail: NoAmount }).detail;
}

export function getEmployerHisaab(token: string, signal?: AbortSignal): Promise<HisaabSummary> {
  return fetch(`/api/hisaab/e/${encodeURIComponent(token)}`, { cache: "no-store", signal }).then((r) =>
    ok<HisaabSummary>(r),
  );
}

export function getCaseHisaab(caseId: number | string, signal?: AbortSignal): Promise<HisaabSummary> {
  return fetch(`/api/hisaab/case/${encodeURIComponent(String(caseId))}`, { cache: "no-store", signal }).then((r) =>
    ok<HisaabSummary>(r),
  );
}

export function propose(
  token: string,
  input: { audio?: Blob; text?: string; amount?: string; month?: string; kind?: HisaabKind },
): Promise<ProposeResult> {
  const form = new FormData();
  if (input.audio) form.append("audio", input.audio, audioUploadName("hisaab", input.audio.type));
  if (input.text) form.append("text", input.text);
  if (input.amount) form.append("amount", input.amount);
  if (input.month) form.append("month", input.month);
  if (input.kind) form.append("kind", input.kind);
  return fetch(`/api/hisaab/e/${encodeURIComponent(token)}`, { method: "POST", body: form }).then((r) =>
    ok<ProposeResult>(r),
  );
}

export function decide(id: number, decision: "accept" | "reject"): Promise<DecideResult> {
  return fetch(`/api/hisaab/${id}/decide`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ decision }),
  }).then((r) => ok<DecideResult>(r));
}
