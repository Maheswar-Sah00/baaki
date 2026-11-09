// Haq Raise (backend: backend/app/routes/raise_.py). Baaki recovers money owed once; a raise changes her pay
// every month. Every amount comes from the backend (G.O.Ms.No.6 estimate via app.wages); nothing is computed here
// except display.

import { ApiError, errorMessage, mediaUrl } from "@/lib/api";

export type RaiseLang = "hi-en" | "te-IN" | "en";
export type RaisePlan = "full" | "step";
export type RaiseStatus = "draft" | "sent" | "played" | "talk" | "accepted" | "stepped";
export type HomeStatus = RaiseStatus | "none" | "fair";

export type RaiseNumbers = {
  work_type: string;
  work_label: string;
  hours_per_day: number;
  days_per_week: number;
  working_days: number;
  current: number;
  legal_estimate: number;
  target: number;
  is_estimate: boolean;
  gap_monthly: number;
  gap_yearly: number;
  per_day: number;
  how: string;
  source: string;
  source_url: string;
};

export type PlanOption = {
  plan: RaisePlan;
  ask: number;
  start: string;
  start_month: string;
  step1: number | null;
  months: number | null;
  step_date: string | null;
  step_month: string | null;
  per_day: number;
  per_day_step1: number | null;
  yearly_gain: number;
  start_display: string | null;
  step_display: string | null;
};

export type RaiseEvent = {
  id: number;
  kind: string;
  direction: string;
  language: string;
  text: string;
  text_worker_lang: string | null;
  audio_url: string | null;
  original_audio_url: string | null;
  data: Record<string, unknown>;
  created_at: string;
};

export type Celebration = {
  title: string;
  title_latin: string;
  text: string;
  speech: string;
  yearly_gain: number;
  yearly_line: string;
  language: RaiseLang;
  new_wage: number;
  final_wage: number;
  audio_url: string | null;
  event_id: number;
  created_at: string;
};

export type RaiseAnswer = {
  choice: "asked" | "step";
  new_wage: number;
  new_wage_from: string;
  step_up_to: number | null;
  step_up_from: string | null;
  answered_at: string;
  yearly_gain: number;
};

export type RaiseView = {
  id: number;
  status: RaiseStatus;
  plan: RaisePlan;
  current: number;
  legal_estimate: number;
  ask_amount: number;
  step1_amount: number | null;
  step_months: number | null;
  start_month: string;
  step_month: string | null;
  mention_law: boolean;
  years_worked: number | null;
  personal_text: string;
  message: {
    lang: RaiseLang;
    text: string;
    sentences: string[];
    disclosure: string;
    source: string | null;
    personal: { included: boolean; display: string } | null;
    text_worker_lang: string | null;
  };
  audio_url: string | null;
  audio_error: unknown;
  employer_path: string;
  employer_url: string;
  share_text: string | null;
  answer: RaiseAnswer | null;
  celebration: Celebration | null;
  agreement_url: string | null;
  ics_url: string | null;
  events: RaiseEvent[];
  yearly_gain_asked: number;
  per_day: number;
  per_day_step1: number | null;
  demo: boolean;
  updated_at: string;
};

export type RaiseCaseView = {
  case_id: number;
  worker: { id: number; name: string; language: RaiseLang };
  employer: { id: number; name: string; language: RaiseLang; name_display: string; name_by_lang: Record<RaiseLang, string> };
  numbers: RaiseNumbers;
  plans: { full: PlanOption | null; step: PlanOption | null };
  raise: RaiseView | null;
  today: string;
};

export type ComposeBody = {
  plan: RaisePlan;
  ask_amount?: number | null;
  step1_amount?: number | null;
  step_months?: number | null;
  mention_law?: boolean;
  years_worked?: number | null;
  personal_text?: string | null;
  personal_lang?: string | null;
  use_llm?: boolean;
  audio?: boolean;
};

export type EmployerRaiseView = {
  raise_id: number;
  status: RaiseStatus;
  worker: { name: string; name_display: string; language: RaiseLang };
  employer: { name: string; name_display: string; language: RaiseLang };
  message: { text: string; sentences: string[]; lang: RaiseLang; disclosure: string };
  audio_url: string | null;
  plan: RaisePlan;
  current: number;
  ask_amount: number;
  step1_amount: number | null;
  start_month: string;
  step_month: string | null;
  start_display: string | null;
  step_display: string | null;
  step_offer: {
    step1: number;
    months: number;
    start_month: string;
    step_month: string;
    start_display: string | null;
    step_display: string | null;
    per_day_step1: number;
  } | null;
  why: {
    per_day: number;
    per_day_text: string;
    per_day_step1: number | null;
    per_day_step1_text: string | null;
    legal_estimate: number | null;
    legal_text: string | null;
    fair_pay_link: string | null;
    fair_pay_text: string | null;
  };
  can_answer: boolean;
  answer: RaiseAnswer | null;
  agreement_url: string | null;
  ics_url: string | null;
  replies: RaiseEvent[];
  ai_notice: string;
};

export type AcceptResponse = {
  status: RaiseStatus;
  answer: RaiseAnswer;
  celebration: Celebration | null;
  agreement_url: string | null;
  ics_url: string | null;
};

export type TalkResponse = {
  status: RaiseStatus;
  transcript: string;
  language: RaiseLang;
  translation: { text: string; language: RaiseLang; source: string; amounts: number[] };
  audio_url: string | null;
  audio_error: unknown;
  original_audio_url: string | null;
  event: RaiseEvent;
};

export type RaiseHome = {
  case_id: number;
  employer: string;
  employer_id: number;
  employer_language: RaiseLang;
  current: number;
  legal_estimate: number;
  target: number;
  is_estimate: boolean;
  gap_monthly: number;
  gap_yearly: number;
  per_day: number;
  hours_per_day: number;
  status: HomeStatus;
  raise_id: number | null;
  new_wage: number | null;
  yearly_gain_won: number;
  url: string;
};

export type RaiseSummary = {
  worker_id: number;
  worker: string;
  language: RaiseLang;
  per_home: RaiseHome[];
  total_yearly_gain_possible: number;
  total_yearly_gain_won: number;
  best_case_id: number | null;
  best_url: string | null;
  best_employer: string | null;
  source_note: string;
};

export type RaiseDemo = {
  case_id: number;
  worker_id: number;
  raise_id: number;
  token: string;
  worker_path: string;
  employer_path: string;
  raise: RaiseView;
};

// ------------------------------------------------------------------ fetch helpers (own, so lib/api.ts stays untouched)
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

function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  return fetch(url, { cache: "no-store", signal }).then((r) => ok<T>(r));
}

function post<T>(url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return fetch(url, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal,
  }).then((r) => ok<T>(r));
}

export const raiseApi = {
  summary: (workerId: number, signal?: AbortSignal) => get<RaiseSummary>(`/api/raise/summary?worker_id=${workerId}`, signal),
  caseView: (caseId: number, signal?: AbortSignal) => get<RaiseCaseView>(`/api/raise/case/${caseId}`, signal),
  compose: (caseId: number, body: ComposeBody, signal?: AbortSignal) =>
    post<RaiseView>(`/api/raise/case/${caseId}/compose`, body, signal),
  sent: (caseId: number) => post<{ ok: boolean; status: RaiseStatus }>(`/api/raise/case/${caseId}/sent`),
  employer: (token: string, signal?: AbortSignal) => get<EmployerRaiseView>(`/api/raise/e/${encodeURIComponent(token)}`, signal),
  played: (token: string) => post<{ ok: boolean; status: RaiseStatus }>(`/api/raise/e/${encodeURIComponent(token)}/played`),
  accept: (token: string, choice: "asked" | "step") =>
    post<AcceptResponse>(`/api/raise/e/${encodeURIComponent(token)}/accept`, { choice }),
  talk: (token: string, input: { audio?: Blob; filename?: string; text?: string; lang?: string }) => {
    const form = new FormData();
    if (input.audio) form.append("audio", input.audio, input.filename ?? "talk.webm");
    if (input.text) form.append("text", input.text);
    if (input.lang) form.append("lang", input.lang);
    return fetch(`/api/raise/e/${encodeURIComponent(token)}/talk`, { method: "POST", body: form }).then((r) =>
      ok<TalkResponse>(r),
    );
  },
  demo: (audio = true) => post<RaiseDemo>("/api/raise/demo", { audio }),
};

// ------------------------------------------------------------------ small helpers
export function media(path: string | null | undefined): string | null {
  return mediaUrl(path);
}

/** The employer raise link on the origin she is using now (tunnels keep working). */
export function raiseLink(path: string): string {
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path}`;
}

export function raiseError(err: unknown): string {
  return errorMessage(err);
}

export function rupees(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "";
  const whole = Math.round(n);
  return `₹${whole.toLocaleString("en-IN")}`;
}

export function isAnswered(status: string | null | undefined): boolean {
  return status === "accepted" || status === "stepped";
}

/** UI language (lib/i18n UiLang) -> the raise language code. */
export function raiseLangOf(lang: string | null | undefined): RaiseLang {
  if (!lang) return "en";
  if (lang.startsWith("te")) return "te-IN";
  if (lang.startsWith("hi")) return "hi-en";
  return "en";
}

export const HTML_LANG: Record<RaiseLang, string> = { "te-IN": "te", "hi-en": "hi", en: "en" };
