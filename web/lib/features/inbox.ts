// Share to Baaki + Promise Keeper (W04 + G16 + W05). Backend: backend/app/routes/inbox.py.
// The employer's WhatsApp reply (voice note or text) -> transcript, translation, read-out, promise, hashed card.
// Reminders are shared by the worker herself; nothing is ever sent automatically.

export type PromiseStatus = "pending" | "passed" | "kept" | "broken";

export type InboxPromise = {
  id: number;
  card_id: number;
  case_id: number;
  amount: number | null;
  amount_display: string | null;
  is_rest: boolean;
  due_date: string;
  due_display: string;
  range_start: string | null;
  precision: "day" | "week" | "month" | string;
  phrase: string;
  quote: string;
  confidence: number;
  confirmed: boolean;
  edited: boolean;
  status: PromiseStatus;
  stored_status: string;
  status_at: string | null;
  reminded_at: string | null;
  can_remind: boolean;
};

export type InboxCard = {
  id: number;
  case_id: number;
  source: "audio" | "text";
  language_code: string;
  stt: { language_code: string | null; detected_language_code: string | null; mode: string | null };
  transcript: string;
  translation: string;
  translation_lang: string;
  translation_source: string;
  amounts: { value: number; text: string; start: number; end: number }[];
  said_on: string;
  audio_url: string | null;
  original_audio_url: string | null;
  summary: { text: string; language: string; text_en: string };
  promise: InboxPromise | null;
  promises: InboxPromise[];
  card: { id: number; hash: string; prev_hash: string; at: string; diary_entry_id: number | null };
};

export type InboxAdded = InboxCard & {
  duplicate: boolean;
  audio: { duration_s: number; voice: string; gnani_calls: number; cache_hits: number } | null;
  audio_error: { message?: string; code?: string } | null;
};

export type InboxList = {
  case: {
    id: number;
    status: string;
    balance: number;
    balance_display: string;
    employer: { name: string; language: string };
    worker: { name: string; language: string };
  };
  as_of: string;
  cards: InboxCard[];
  promises: InboxPromise[];
  passed: InboxPromise[];
  counts: Record<PromiseStatus, number>;
  chain: { valid: boolean; broken_at: number | null; head: string | null; count: number; cards_linked: boolean };
};

export type Reminder = {
  text: string;
  language: string;
  text_worker_lang: string;
  worker_language: string;
  share_text: string;
  employer_url: string;
  whatsapp_url: string;
  source: string;
  checks: { amounts_ok: boolean; no_accusation: boolean; amounts_expected: number[]; amounts_found: number[] };
  promise: InboxPromise;
};

export type ReplyLang = "employer" | "auto" | "hi-en" | "te-IN" | "en";

export class InboxError extends Error {
  status: number;
  code: string | null;
  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "InboxError";
    this.status = status;
    this.code = code;
  }
}

async function ok<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let message = `${res.status}`;
  let code: string | null = null;
  try {
    const body = (await res.json()) as { detail?: unknown };
    const d = body?.detail;
    if (typeof d === "string") message = d;
    else if (d && typeof d === "object") {
      const o = d as { message?: string; error?: string; error_code?: string };
      message = o.message ?? message;
      code = o.error ?? o.error_code ?? null;
    }
  } catch {
    /* keep the status */
  }
  throw new InboxError(message, res.status, code);
}

const q = (asOf?: string | null) => (asOf ? `?as_of=${encodeURIComponent(asOf)}` : "");

export async function getInbox(caseId: number, asOf?: string | null, signal?: AbortSignal): Promise<InboxList> {
  return ok(await fetch(`/api/inbox/${caseId}${q(asOf)}`, { cache: "no-store", signal }));
}

export async function addReply(
  caseId: number,
  input: { audio?: Blob | File | null; filename?: string; text?: string; lang?: ReplyLang; saidOn?: string | null },
  signal?: AbortSignal,
): Promise<InboxAdded> {
  const fd = new FormData();
  if (input.audio) {
    const name = input.filename ?? (input.audio instanceof File ? input.audio.name : "reply.webm");
    fd.append("audio", input.audio, name);
  }
  if (input.text) fd.append("text", input.text);
  if (input.lang && input.lang !== "employer") fd.append("lang", input.lang);
  if (input.saidOn) fd.append("said_on", input.saidOn);
  return ok(await fetch(`/api/inbox/${caseId}`, { method: "POST", body: fd, cache: "no-store", signal }));
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  return ok(
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    }),
  );
}

export function makeReminder(promiseId: number, asOf?: string | null): Promise<Reminder> {
  return postJson(`/api/inbox/promises/${promiseId}/remind`, { as_of: asOf ?? null });
}

export function setPromise(
  promiseId: number,
  patch: { status?: "pending" | "kept" | "broken"; confirmed?: boolean; due_date?: string; amount?: number; clear_amount?: boolean; as_of?: string | null },
): Promise<InboxPromise> {
  return postJson(`/api/inbox/promises/${promiseId}/status`, patch);
}

/** Pill tone for a promise status (design-system StatusPill tones). */
export function promiseTone(status: PromiseStatus): "neutral" | "accent" | "success" | "warn" | "error" {
  switch (status) {
    case "kept":
      return "success";
    case "passed":
      return "warn";
    case "broken":
      return "error";
    default:
      return "accent";
  }
}
