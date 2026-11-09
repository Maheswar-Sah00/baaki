// Exit Kit (W03 lite) client: POST /api/exit, GET /api/exit/{id}, the gate checklist audio, and the
// one-tap Polite step built from the EXISTING case / message / diary endpoints in lib/api.ts.

import { ApiError, addDiary, confirmCase, createCase, makeStep } from "@/lib/api";
import type { CaseCreate, Facts, StepResponse } from "@/lib/types";

export type ExitItem = {
  kind: "final_settlement" | "unpaid_wage" | "illegal_deduction" | "advance_recovery" | "paid_back" | "min_wage_shortfall" | string;
  month: string | null;
  amount: number;
  is_estimate: boolean;
  included_in_total: boolean;
  label: string;
  basis: string;
  source: string;
  due_date: string | null;
  days_worked?: number;
  days_how?: string;
  from_case?: boolean;
};

export type ChecklistItem = {
  id: "amount" | "last_day" | "ledger_photo" | "contact" | string;
  text: string;
  lang: string;
  audio_url: string | null;
  tts_error: unknown;
  duration_s?: number;
};

export type ExitPolite =
  | { mode: "nothing_due" }
  | { mode: "update_case"; case_id: number; confirm: { confirmed: boolean; facts: Facts }; then: string }
  | { mode: "new_case"; create: CaseCreate; then: string };

export type ExitResult = {
  id: number;
  lang: string;
  last_day: string;
  last_day_how: "given" | "from_tomorrow" | "said" | "day_before" | "today" | string;
  month: string;
  due_by: string;
  due_weekday: string;
  basis: {
    due_rule: string;
    due_note: string;
    our_reading: string;
    part_month: string | null;
    days_worked: number;
    days_how: "you said" | "diary check-ins" | "calendar count" | string;
    divisor: number;
    monthly_wage: number;
    not_claimed: string;
  };
  items: ExitItem[];
  total: number;
  shortfall_estimate_not_in_total: number;
  is_estimate_flags: Record<string, boolean>;
  notes: string[];
  checklist: ChecklistItem[];
  checklist_audio: "cached" | "text_only";
  sources: string[];
  disclaimer: string;
  worker: { id: number; name: string; language: string };
  employer: { id: number; name: string; language: string; phone: string | null } | null;
  case_id: number | null;
  safety: { ok?: boolean; flagged?: boolean; categories?: string[] } | null;
  polite: ExitPolite;
};

export type ExitIn = {
  worker_id: number;
  employer_id?: number | null;
  case_id?: number | null;
  last_day?: string | null;
  days_worked_this_month?: number | null;
  monthly_wage?: number | null;
  transcript?: string;
  lang?: string | null;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = null;
    let message = `${res.status} ${res.statusText || "error"}`.trim();
    try {
      body = await res.json();
      const d = (body as { detail?: unknown })?.detail;
      if (typeof d === "string") message = d;
    } catch {
      /* keep the fallback */
    }
    throw new ApiError(message, res.status, body, null);
  }
  return (await res.json()) as T;
}

function post<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  }).then((r) => json<T>(r));
}

/** POST /api/exit: due date, what is owed, the checklist (cached audio only). No Gnani call. */
export function computeExit(body: ExitIn, signal?: AbortSignal): Promise<ExitResult> {
  const clean = Object.fromEntries(Object.entries(body).filter(([, v]) => v !== null && v !== undefined && v !== ""));
  return post<ExitResult>("/api/exit", clean, signal);
}

export function getExit(id: number, lang?: string, signal?: AbortSignal): Promise<ExitResult> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return fetch(`/api/exit/${id}${q}`, { cache: "no-store", signal }).then((r) => json<ExitResult>(r));
}

/** POST /api/exit/checklist: speak the missing items once (Timbre cache). Failures come back as text only. */
export function speakChecklist(lang: string, signal?: AbortSignal): Promise<{ checklist: ChecklistItem[]; fallback: string | null; tts_calls: number }> {
  return post("/api/exit/checklist", { lang }, signal);
}

/** UI language -> backend checklist language. */
export function exitLangOf(ui: string): string {
  if (ui.startsWith("te")) return "te-IN";
  if (ui.startsWith("en")) return "en-IN";
  return "hi-en";
}

/**
 * One tap: put the exit amount on the case and make the NORMAL Polite step.
 *   existing case: POST /api/cases/{id}/confirm {facts}  -> POST /api/cases/{id}/messages/polite
 *   no case:       POST /api/cases {facts} -> confirm    -> POST /api/cases/{id}/messages/polite
 * Also writes a dated note to the hash-chained diary (POST /api/diary). Returns the case id; the
 * message may be null if the voice service is busy (the case screen can retry it).
 */
export async function startPolite(
  result: ExitResult,
  note: string,
): Promise<{ caseId: number; message: StepResponse | null; error: unknown }> {
  const plan = result.polite;
  let caseId: number;
  if (plan.mode === "update_case") {
    await confirmCase(plan.case_id, plan.confirm);
    caseId = plan.case_id;
  } else if (plan.mode === "new_case") {
    const made = await createCase(plan.create);
    await confirmCase(made.id, { confirmed: true });
    caseId = made.id;
  } else {
    throw new Error("nothing_due");
  }
  try {
    await addDiary({ workerId: result.worker.id, employerId: result.employer?.id ?? null, caseId, kind: "note", text: note });
  } catch {
    /* the diary note is a bonus; never block the message on it */
  }
  try {
    const message = await makeStep(caseId, "polite");
    return { caseId, message, error: null };
  } catch (error) {
    return { caseId, message: null, error };
  }
}
