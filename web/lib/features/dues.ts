// Baaki for every promise: the second door (backend: backend/app/routes/dues.py).
// Small sums people keep promising "next month, first week" / "by the end of this week": the milkman's customers,
// a chit agent's payout. Amounts come from the backend's deterministic parsers; reminders are shared by the user.

import { settingsStore } from "@/lib/store";

export type DuesKind = "vendor" | "chit" | "other";
export type DuesLang = "hi-en" | "te-IN" | "en";
export type PromiseStatus = "pending" | "kept" | "broken";
export type ByLang = Record<DuesLang, string>;

export type ParsedItem = {
  label: string;
  item_key: string | null;
  month: number | null;
  amount: number;
  source_text: string;
  display: ByLang;
};

export type ParsedPromise = {
  due_date: string;
  range_start: string | null;
  precision: string;
  phrase: string;
  quote: string;
  lang: DuesLang;
  amount: number | null;
};

export type ParseResult = {
  lang: DuesLang;
  items: ParsedItem[];
  total: number;
  total_display: string;
  transcript: string;
  stt: { language_code: string | null; detected_language_code: string | null; mode: string | null } | null;
  promise: ParsedPromise | null;
  kind: DuesKind;
};

export type DuesItem = {
  id: number;
  kind: "due" | "paid";
  label: string;
  item_key: string | null;
  month: number | null;
  amount: number;
  amount_display: string;
  source_text: string;
  said_on: string;
  display: ByLang;
  hash: string;
};

export type DuesPromise = {
  id: number;
  said_on: string;
  due_date: string;
  range_start: string | null;
  precision: string;
  phrase: string;
  quote: string;
  lang: DuesLang;
  amount: number | null;
  amount_display: string | null;
  source: "text" | "audio";
  stored_status: PromiseStatus;
  status: PromiseStatus;
  status_at: string | null;
  hash: string;
  said_display: ByLang;
  due_display: ByLang;
};

export type DuesCounter = {
  made: number;
  broken: number;
  kept: number;
  pending: number;
  first_promised: string | null;
  months_ago: number;
  days_ago: number;
  text_en: string;
};

export type DuesView = {
  account: {
    id: number;
    kind: DuesKind;
    title: string;
    party_name: string;
    party_lang: DuesLang;
    party_phone: string | null;
    owner_name: string;
    owner_lang: DuesLang;
    owner_vpa: string | null;
    note: string;
    demo: boolean;
    created_at: string;
    party_display: ByLang;
  };
  as_of: string;
  items: DuesItem[];
  total_due: number;
  total_paid: number;
  balance: number;
  balance_display: string;
  promises: DuesPromise[];
  last_promise: DuesPromise | null;
  counter: DuesCounter;
  chain: { valid: boolean; broken_at: number | null; head: string | null; count: number };
  upi_url: string | null;
  pack: { eligible: boolean; min_broken: number; applies: boolean; url: string };
  can_remind: boolean;
  added_promise_id?: number;
};

export type DuesSummary = {
  id: number;
  kind: DuesKind;
  title: string;
  party_name: string;
  party_display: ByLang;
  party_lang: DuesLang;
  owner_name: string;
  balance: number;
  balance_display: string;
  items: number;
  item_labels: ByLang[];
  promises_made: number;
  promises_broken: number;
  first_promised: string | null;
  months_ago: number;
  last_due: string | null;
  last_status: PromiseStatus | null;
  pack_eligible: boolean;
  demo: boolean;
};

export type DuesList = {
  as_of: string;
  accounts: DuesSummary[];
  by_kind: Record<DuesKind, { count: number; balance: number; broken: number }>;
  total: number;
  total_display: string;
  promises_broken: number;
};

export type DuesReminder = {
  text: string;
  sentences: string[];
  language: DuesLang;
  share_text: string;
  checks: { amounts_ok: boolean; no_accusation: boolean; amounts_expected: number[]; amounts_found: number[] };
  source: string;
  items_listed: boolean;
  quoted_promise: boolean;
  text_owner_lang: string;
  owner_language: DuesLang;
  upi_url: string | null;
  whatsapp_url: string;
  audio_url: string | null;
  audio: { duration_s: number; voice: string; gnani_calls: number; cache_hits: number; disclosure: string } | null;
  audio_error: { message?: string } | null;
};

export class DuesError extends Error {
  status: number;
  code: string | null;
  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "DuesError";
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
  throw new DuesError(message, res.status, code);
}

const q = (asOf?: string | null) => (asOf ? `?as_of=${encodeURIComponent(asOf)}` : "");

/** Dues accounts belong to a worker (backend DuesOwner): every list / create / demo call names her. */
function currentWorkerId(): number {
  return settingsStore.get().workerId;
}
const qw = (asOf?: string | null, workerId: number = currentWorkerId()) => {
  const p = new URLSearchParams({ worker_id: String(workerId) });
  if (asOf) p.set("as_of", asOf);
  return `?${p.toString()}`;
};

async function postJson<T>(url: string, body: unknown): Promise<T> {
  return ok(
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    }),
  );
}

export async function listDues(asOf?: string | null, signal?: AbortSignal, workerId?: number): Promise<DuesList> {
  return ok(await fetch(`/api/dues${qw(asOf, workerId)}`, { cache: "no-store", signal }));
}

export async function getDues(id: number, asOf?: string | null, signal?: AbortSignal): Promise<DuesView> {
  return ok(await fetch(`/api/dues/${id}${q(asOf)}`, { cache: "no-store", signal }));
}

/** Speak (audio) or type (text) -> chips + running total. Nothing is saved. */
export async function parseDues(input: {
  text?: string;
  audio?: Blob | null;
  filename?: string;
  lang?: "te" | "hinglish" | "en" | "auto";
  kind: DuesKind;
  party?: string;
}): Promise<ParseResult> {
  const fd = new FormData();
  if (input.audio) fd.append("audio", input.audio, input.filename ?? "clip.webm");
  if (input.text) fd.append("text", input.text);
  fd.append("lang", input.lang ?? "auto");
  fd.append("kind", input.kind);
  if (input.party) fd.append("party", input.party);
  return ok(await fetch("/api/dues/parse", { method: "POST", body: fd, cache: "no-store" }));
}

export type NewDues = {
  /** Defaults to the remembered worker (settings). */
  worker_id?: number;
  kind: DuesKind;
  party_name: string;
  party_lang: DuesLang;
  party_phone?: string | null;
  owner_name?: string;
  owner_lang?: DuesLang;
  owner_vpa?: string | null;
  title?: string;
  items: { label: string; amount: number; item_key?: string | null; month?: number | null; source_text?: string }[];
  promise_text?: string | null;
};

export function createDues(body: NewDues): Promise<DuesView> {
  return postJson("/api/dues", { ...body, worker_id: body.worker_id ?? currentWorkerId() });
}

export async function addPromise(
  id: number,
  input: { text?: string; audio?: Blob | null; filename?: string; saidOn?: string | null; dueDate?: string | null; lang?: string | null; asOf?: string | null },
): Promise<DuesView> {
  const fd = new FormData();
  if (input.audio) fd.append("audio", input.audio, input.filename ?? "promise.webm");
  if (input.text) fd.append("text", input.text);
  if (input.saidOn) fd.append("said_on", input.saidOn);
  if (input.dueDate) fd.append("due_date", input.dueDate);
  if (input.lang) fd.append("lang", input.lang);
  if (input.asOf) fd.append("as_of", input.asOf);
  return ok(await fetch(`/api/dues/${id}/promises`, { method: "POST", body: fd, cache: "no-store" }));
}

export function addPaid(id: number, amount: number, asOf?: string | null): Promise<DuesView> {
  return postJson(`/api/dues/${id}/paid`, { amount, as_of: asOf ?? null });
}

export function setPromiseStatus(promiseId: number, status: PromiseStatus, asOf?: string | null): Promise<DuesView> {
  return postJson(`/api/dues/promises/${promiseId}/status`, { status, as_of: asOf ?? null });
}

export function makeReminder(id: number, opts: { lang?: DuesLang | null; voice?: boolean; asOf?: string | null }): Promise<DuesReminder> {
  return postJson(`/api/dues/${id}/remind`, { lang: opts.lang ?? null, voice: !!opts.voice, as_of: opts.asOf ?? null });
}

export function loadDemo(workerId?: number): Promise<{ accounts: { milk: number; chit: number }; as_of: string }> {
  return postJson(`/api/dues/demo${qw(null, workerId)}`, {});
}

export async function deleteDues(id: number): Promise<{ deleted: number }> {
  return ok(await fetch(`/api/dues/${id}`, { method: "DELETE", cache: "no-store" }));
}

export function packUrl(id: number, asOf?: string | null): string {
  return `/api/dues/${id}/pack.pdf${q(asOf)}`;
}

/** UI language (lib/i18n UiLang) -> the backend's message language. */
export function duesLang(ui: string): DuesLang {
  return ui === "te" ? "te-IN" : ui === "hi-en" ? "hi-en" : "en";
}

export function sttLang(l: DuesLang): "te" | "hinglish" | "en" {
  return l === "te-IN" ? "te" : l === "hi-en" ? "hinglish" : "en";
}

export function promiseTone(status: PromiseStatus): "accent" | "success" | "error" {
  return status === "kept" ? "success" : status === "broken" ? "error" : "accent";
}
