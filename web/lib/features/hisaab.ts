// V09 Hisaab Milao (backend: backend/app/routes/hisaab.py). The employer proposes a correction by voice or typing;
// the worker hears it in her language and accepts or rejects. Every amount and month comes from the backend
// (app.lang parsers); nothing is computed here except display.

import { ApiError, audioUploadName } from "@/lib/api";

export type HisaabKind = "cash" | "upi" | "advance" | "other";
export type HisaabStatus = "proposed" | "accepted" | "rejected";

export type HisaabProposal = {
  id: number;
  case_id: number;
  status: HisaabStatus;
  display_state: "proposed" | "accepted" | "disputed";
  said_by: "employer";
  said_by_name: string;
  said_by_label: string;
  amount: number;
  amount_display: string;
  signed_display: string;
  amount_source: "spoken" | "typed";
  kind: HisaabKind;
  month: string | null;
  month_label: string | null;
  transcript: string;
  source: "voice" | "text";
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
};

export type HisaabSummary = HisaabMoney & {
  case_id: number;
  worker: { name: string; language: string };
  employer: { name: string; language: string };
  proposals: HisaabProposal[];
  pending: number;
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
