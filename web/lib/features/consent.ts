// G13 "Her spoken consent IS the voice sample": client for /api/consent.
// She repeats the consent sentence; the same recording is the consent record and the clone sample.
// A failed match never blocks: retry, or confirm by tap (method=tap with the same recording).

import { ApiError, audioUploadName } from "@/lib/api";

export type ConsentLang = "te-IN" | "hi-en" | "en";

export type ConsentWord = {
  i: number;
  text: string;
  kind: "name" | "content" | "filler";
  /** null = not checked yet (or a filler word); true = heard; false = missed */
  matched: boolean | null;
  score?: number;
  heard?: string | null;
};

export type ConsentMatch = {
  passed: boolean;
  lang: ConsentLang;
  name_matched: boolean;
  content_matched: number;
  content_total: number;
  ratio: number;
  threshold: number;
  words: ConsentWord[];
  missed: string[];
  reason: "name_not_heard" | "too_few_words" | null;
};

export type ConsentLogEntry = {
  diary_entry_id: number;
  timestamp: string;
  event: "given" | "withdrawn";
  consent_method: "spoken" | "tap" | string | null;
  text: string;
  audio_sha256: string | null;
  hash: string;
  prev_hash: string;
};

export type ConsentProfile = {
  exists: boolean;
  profile_id?: number;
  consent_at?: string;
  duration_s?: number;
  audio_stored?: boolean;
  trimmed_to_20s?: boolean;
  [k: string]: unknown;
};

export type ConsentPrompt = { audio_url: string | null; duration_s: number | null; cached: boolean; tts_error?: unknown };

export type ConsentStatus = {
  worker_id: number;
  lang: ConsentLang;
  name: string;
  text: string;
  sentences: string[];
  meaning_en: string;
  words: ConsentWord[];
  duration_hint_s: [number, number];
  prompt: ConsentPrompt | null;
  profile: ConsentProfile;
  consent_active: boolean;
  log: ConsentLogEntry[];
};

export type AttemptResult = {
  status: "ready" | "not_matched" | "too_short" | "too_long";
  worker_id: number;
  lang: ConsentLang;
  method: "spoken" | "tap";
  audio_sha256: string;
  audio_stored: false;
  duration_s?: number;
  transcript?: string;
  match?: ConsentMatch | null;
  words: ConsentWord[];
  missed?: string[];
  stt_error?: unknown;
  can_retry: boolean;
  can_confirm_by_tap: boolean;
  message: string;
  consent_method?: "spoken" | "tap";
  consent?: ConsentLogEntry;
  profile?: ConsentProfile;
};

export type WithdrawResult = { worker_id: number; deleted: number; logged: boolean; consent: ConsentLogEntry | null };

async function ok<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let body: unknown = null;
  let message = `${res.status} ${res.statusText || "error"}`;
  let code: string | null = null;
  try {
    body = await res.json();
    const d = (body as { detail?: unknown })?.detail;
    if (typeof d === "string") message = d;
    else if (d && typeof d === "object") {
      const o = d as { message?: unknown; error?: unknown };
      if (typeof o.message === "string") message = o.message;
      if (typeof o.error === "string") code = o.error;
    }
  } catch {
    /* keep fallback */
  }
  throw new ApiError(message, res.status, body, code);
}

export function getConsent(workerId: number, lang?: ConsentLang | null, signal?: AbortSignal): Promise<ConsentStatus> {
  const q = new URLSearchParams({ worker_id: String(workerId) });
  if (lang) q.set("lang", lang);
  return fetch(`/api/consent?${q}`, { cache: "no-store", signal }).then((r) => ok<ConsentStatus>(r));
}

function postJson<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  }).then((r) => ok<T>(r));
}

/** Timbre reads the sentence slowly (cached on the server after the first time). */
export function getPrompt(workerId: number, lang?: ConsentLang | null, signal?: AbortSignal) {
  return postJson<ConsentPrompt & { text: string }>("/api/consent/prompt", { worker_id: workerId, lang }, signal);
}

/** One recording. method "tap" re-sends the SAME blob after a failed match (no second STT call). */
export function sendAttempt(
  workerId: number,
  audio: Blob,
  opts: { lang?: ConsentLang | null; method?: "spoken" | "tap"; filename?: string } = {},
  signal?: AbortSignal,
): Promise<AttemptResult> {
  const form = new FormData();
  form.append("worker_id", String(workerId));
  form.append("method", opts.method ?? "spoken");
  if (opts.lang) form.append("lang", opts.lang);
  form.append("audio", audio, audioUploadName(opts.filename ?? "consent", audio.type));
  return fetch("/api/consent/attempt", { method: "POST", body: form, signal }).then((r) => ok<AttemptResult>(r));
}

export function withdrawConsent(workerId: number, signal?: AbortSignal): Promise<WithdrawResult> {
  return postJson<WithdrawResult>("/api/consent/withdraw", { worker_id: workerId }, signal);
}

export const CONSENT_LANGS: { id: ConsentLang; label: string }[] = [
  { id: "te-IN", label: "తెలుగు" },
  { id: "hi-en", label: "हिंदी / Hinglish" },
  { id: "en", label: "English" },
];
