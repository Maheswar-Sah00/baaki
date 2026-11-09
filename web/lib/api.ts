// Typed client for the Baaki FastAPI backend. Every call goes to the same origin (/api/*), which
// Next rewrites to the backend (next.config.ts). No API keys ever live in the browser.
// One function per backend endpoint; shapes live in lib/types.ts.

import type {
  CaseCreate,
  CaseDetail,
  Dashboard,
  DemoReset,
  DiaryAdded,
  DiaryKind,
  DiaryList,
  EmployerPage,
  ExtractResponse,
  Facts,
  Health,
  LadderStep,
  LangCode,
  ListenLang,
  ListenResponse,
  MessageView,
  MeterChip,
  MeterResponse,
  PayIn,
  PayResponse,
  PlanResponse,
  ReadbackAudio,
  ReplyResponse,
  StepOptions,
  StepResponse,
  SttChunk,
  VoiceProfileDeleted,
  VoiceProfileView,
  Worker,
} from "./types";
import { currentWorkerKey, setWorker } from "./store";

export type { Health } from "./types";

// ------------------------------------------------------------------ worker key on every request
// A public deploy (BAAKI_PUBLIC=1) opens a worker's data only with her key. One mechanism for every caller
// (this file, lib/features/*.ts, components): a same-origin /api fetch gets X-Baaki-Key when a key is stored.
// No key (the synthetic demo workers, or localhost): requests are untouched.
const KEY_HEADER = "X-Baaki-Key";

function isOwnApi(url: string): boolean {
  if (url.startsWith("/api/")) return true;
  try {
    const u = new URL(url, window.location.href);
    return u.origin === window.location.origin && u.pathname.startsWith("/api/");
  } catch {
    return false;
  }
}

function installKeyHeader() {
  if (typeof window === "undefined") return;
  const w = window as Window & { __baakiKeyFetch?: boolean };
  if (w.__baakiKeyFetch) return;
  w.__baakiKeyFetch = true;
  const original = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const key = currentWorkerKey();
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (!key || !isOwnApi(url)) return original(input, init);
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    if (!headers.has(KEY_HEADER)) headers.set(KEY_HEADER, key);
    return original(input, { ...init, headers });
  };
}

installKeyHeader();

// ------------------------------------------------------------------ errors
export class ApiError extends Error {
  status: number;
  body: unknown;
  /** Machine code from the backend, e.g. "nothing_due", "consent_required", "no_speech". */
  code: string | null;
  constructor(message: string, status: number, body: unknown = null, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
  }
}

function pickMessage(detail: unknown): { message: string | null; code: string | null } {
  if (typeof detail === "string") return { message: detail, code: null };
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg, type}]
    const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined;
    return { message: first?.msg ? `${first.msg} (${(first.loc ?? []).join(".")})` : null, code: "validation" };
  }
  if (detail && typeof detail === "object") {
    const o = detail as { message?: unknown; error?: unknown; detail?: unknown };
    const code = typeof o.error === "string" ? o.error : null;
    if (typeof o.message === "string") return { message: o.message, code };
    if (o.detail !== undefined) {
      const inner = pickMessage(o.detail);
      return { message: inner.message, code: code ?? inner.code };
    }
    return { message: JSON.stringify(detail).slice(0, 300), code };
  }
  return { message: null, code: null };
}

async function ensureOk(res: Response): Promise<Response> {
  if (res.ok) return res;
  let message = `${res.status} ${res.statusText || "error"}`.trim();
  let body: unknown = null;
  let code: string | null = null;
  try {
    const text = await res.text();
    if (text) {
      try {
        body = JSON.parse(text);
        const o = body as { detail?: unknown };
        const picked = pickMessage(o?.detail ?? body);
        code = picked.code;
        if (picked.message) message = picked.message;
      } catch {
        message = `${res.status}: ${text.slice(0, 300)}`;
      }
    }
  } catch {
    /* keep the fallback message */
  }
  throw new ApiError(message, res.status, body, code);
}

/** True when the voice service (Gnani) or the backend is busy / down: text features still work. */
export function isVoiceServiceError(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 502 || err.status === 503 || err.status === 504);
}

export function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (isVoiceServiceError(err)) {
      return `The voice service is busy (${err.status}). Try again in a moment, or type instead.`;
    }
    if (err.status === 500 && /^500/.test(err.message)) {
      return "The server is not answering. Is the backend running?";
    }
    return err.message;
  }
  if (err instanceof TypeError) return "No connection to the server. Check the internet and try again.";
  if (err instanceof Error) return err.message;
  return String(err);
}

// ------------------------------------------------------------------ helpers
function now(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await ensureOk(await fetch(url, { cache: "no-store", signal }));
  return (await res.json()) as T;
}

async function sendJson<T>(method: "POST" | "DELETE", url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await ensureOk(
    await fetch(url, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal,
    }),
  );
  return (await res.json()) as T;
}

async function sendForm<T>(url: string, form: FormData, signal?: AbortSignal): Promise<T> {
  const res = await ensureOk(await fetch(url, { method: "POST", body: form, signal }));
  return (await res.json()) as T;
}

/** Give an uploaded audio blob a filename with an extension the backend accepts. */
export function audioUploadName(name: string, type: string): string {
  if (/\.[a-z0-9]{2,5}$/i.test(name)) return name;
  const ext =
    type.includes("ogg") || type.includes("opus")
      ? "ogg"
      : type.includes("mpeg")
        ? "mp3"
        : type.includes("mp4") || type.includes("aac")
          ? "m4a"
          : "webm";
  return `${name || "voice-message"}.${ext}`;
}

function appendAudio(form: FormData, audio: Blob, filename = "recording") {
  form.append("audio", audio, audioUploadName(filename, audio.type));
}

/** Backend media paths ("/api/media/...") are same-origin through the Next proxy. */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) {
    // The backend builds absolute links from PUBLIC_BASE_URL; keep only the path so tunnels work.
    try {
      const u = new URL(path);
      return u.pathname + u.search;
    } catch {
      return path;
    }
  }
  return path.startsWith("/") ? path : `/${path}`;
}

/** A stored media key (Message.audio_path / pdf_path, e.g. "c1/abc.ogg") -> its same-origin URL. */
export function mediaKeyUrl(key: string | null | undefined): string | null {
  if (!key) return null;
  if (key.startsWith("/") || /^https?:/i.test(key)) return mediaUrl(key);
  return `/api/media/${key}`;
}

/** The public employer link for sharing, built on the origin the worker is using now. */
export function employerLink(employerPath: string): string {
  const path = mediaUrl(employerPath) ?? employerPath;
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path}`;
}

// ------------------------------------------------------------------ health / voice primitives
export function getHealth(signal?: AbortSignal): Promise<Health> {
  return getJson<Health>("/api/health", signal);
}

export type SttResponse = {
  transcript: string;
  detected_language_code: string | null;
  language_code: string;
  mode: string;
  chunks: SttChunk[];
  duration_s: number;
  model: string;
};
export type SttLang = "te" | "hinglish" | "auto" | "indic-auto";
export type SttMode = "transcribe" | "codemix" | "verbatim" | "transliterate";
export type TtsLang = "te-IN" | "hi-IN" | "hi-en" | "en-IN";
export type TtsModel = "timbre-v3.0" | "timbre-v2.5";
export type TtsFormat = "ogg" | "mp3";

/** Raw STT (not used by the screens; /api/cases/listen wraps it). */
export async function postStt(
  audio: Blob,
  filename: string,
  opts: { lang?: SttLang | string; mode?: SttMode } = {},
  signal?: AbortSignal,
): Promise<{ data: SttResponse; ms: number }> {
  const form = new FormData();
  appendAudio(form, audio, filename);
  if (opts.lang) form.append("lang", opts.lang);
  if (opts.mode) form.append("mode", opts.mode);
  const t0 = now();
  const data = await sendForm<SttResponse>("/api/stt", form, signal);
  return { data, ms: Math.round(now() - t0) };
}

/** Timbre TTS through the backend cache. Returns audio bytes. */
export async function postTts(
  body: { text: string; lang: TtsLang; voice?: string; model?: TtsModel; format?: TtsFormat },
  signal?: AbortSignal,
): Promise<{ blob: Blob; durationS: number | null; voice: string | null; ms: number }> {
  const t0 = now();
  const res = await ensureOk(
    await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
  );
  const raw = await res.blob();
  // Re-wrap with a clean MIME: Web Share on Android rejects "audio/ogg; codecs=opus".
  const type = body.format === "mp3" ? "audio/mpeg" : "audio/ogg";
  const blob = raw.type === type ? raw : new Blob([raw], { type });
  const dur = Number.parseFloat(res.headers.get("x-duration-s") ?? "");
  return {
    blob,
    durationS: Number.isFinite(dur) ? dur : null,
    voice: res.headers.get("x-tts-voice"),
    ms: Math.round(now() - t0),
  };
}

/** Map any language code to a Timbre language. */
export function ttsLangOf(lang: string | null | undefined): TtsLang {
  if (!lang) return "te-IN";
  if (lang.startsWith("te")) return "te-IN";
  if (lang === "hi-IN") return "hi-IN";
  if (lang.startsWith("en")) return "en-IN";
  return "hi-en";
}

// ------------------------------------------------------------------ cases: listen / meter / extract
/** POST /api/cases/listen: audio -> transcript + Baaki Meter chips + safety. Spends one Gnani STT call. */
export function listen(
  audio: Blob,
  opts: { lang?: ListenLang; useLlm?: boolean; filename?: string } = {},
  signal?: AbortSignal,
): Promise<ListenResponse> {
  const form = new FormData();
  appendAudio(form, audio, opts.filename ?? "recording");
  form.append("lang", opts.lang ?? "auto");
  form.append("use_llm", String(opts.useLlm ?? true));
  return sendForm<ListenResponse>("/api/cases/listen", form, signal);
}

/** POST /api/cases/meter: text -> chips (no LLM, a few ms). With `chips`, re-totals edited chips. */
export function meter(
  body: { text?: string; lang?: string | null; chips?: MeterChip[] | null },
  signal?: AbortSignal,
): Promise<MeterResponse> {
  return sendJson<MeterResponse>(
    "POST",
    "/api/cases/meter",
    { text: body.text ?? "", lang: body.lang ?? null, chips: body.chips ?? null },
    signal,
  );
}

/** POST /api/cases/extract: text -> proposed facts + calculation preview + read-back text. */
export function extract(
  body: { text: string; lang?: string | null; worker_lang?: string | null; use_llm?: boolean; include_shortfall?: boolean },
  signal?: AbortSignal,
): Promise<ExtractResponse> {
  return sendJson<ExtractResponse>("POST", "/api/cases/extract", body, signal);
}

// ------------------------------------------------------------------ cases: create / get / readback / confirm
export function createCase(body: CaseCreate, signal?: AbortSignal): Promise<CaseDetail> {
  return sendJson<CaseDetail>("POST", "/api/cases", body, signal);
}

export function getCase(caseId: number, signal?: AbortSignal): Promise<CaseDetail> {
  return getJson<CaseDetail>(`/api/cases/${caseId}`, signal);
}

/** POST /api/cases/{id}/readback. audio=false returns text only (no Gnani call). */
export function readback(
  caseId: number,
  body: { lang?: LangCode | null; voice?: string | null; audio?: boolean } = {},
  signal?: AbortSignal,
): Promise<ReadbackAudio> {
  return sendJson<ReadbackAudio>("POST", `/api/cases/${caseId}/readback`, body, signal);
}

/** POST /api/cases/{id}/confirm. confirmed=false + facts/include_shortfall just recalculates. */
export function confirmCase(
  caseId: number,
  body: { confirmed?: boolean; facts?: Facts | null; include_shortfall?: boolean | null } = {},
  signal?: AbortSignal,
): Promise<CaseDetail> {
  return sendJson<CaseDetail>("POST", `/api/cases/${caseId}/confirm`, body, signal);
}

/** GET /api/cases/{id}/legal-pack: a PDF; open this URL directly. */
export function legalPackUrl(caseId: number, useLlm = true): string {
  return `/api/cases/${caseId}/legal-pack${useLlm ? "" : "?use_llm=false"}`;
}

// ------------------------------------------------------------------ workers / dashboard / demo
export function getWorker(workerId: number, signal?: AbortSignal): Promise<Worker> {
  return getJson<Worker>(`/api/workers/${workerId}`, signal);
}

export function getDashboard(workerId: number, signal?: AbortSignal): Promise<Dashboard> {
  return getJson<Dashboard>(`/api/workers/${workerId}/dashboard`, signal);
}

export type Onboarded = { worker_id: number; key: string; name: string; language: string; key_header: string; note: string };

/** POST /api/onboard: a new worker and her secret key (returned once). Stores both, so every later request
 * carries X-Baaki-Key. */
export async function onboard(
  body: { name: string; language: "te-IN" | "hi-en" | "hi-IN" | "en-IN"; work_type?: string },
  signal?: AbortSignal,
): Promise<Onboarded> {
  const out = await sendJson<Onboarded>("POST", "/api/onboard", body, signal);
  setWorker(out.worker_id, out.key);
  return out;
}

/** POST /api/demo/reset: wipes every table and re-seeds the synthetic story (admin-only on a public deploy). */
export function resetDemo(signal?: AbortSignal): Promise<DemoReset> {
  return sendJson<DemoReset>("POST", "/api/demo/reset", undefined, signal);
}

// ------------------------------------------------------------------ ladder messages
/** POST /api/cases/{id}/messages/{step}: text (employer's language), voice note and PDF. */
export function makeStep(caseId: number, step: LadderStep, opts: StepOptions = {}, signal?: AbortSignal): Promise<StepResponse> {
  return sendJson<StepResponse>("POST", `/api/cases/${caseId}/messages/${step}`, opts, signal);
}

export function listMessages(caseId: number, signal?: AbortSignal): Promise<{ case_id: number; messages: MessageView[] }> {
  return getJson(`/api/cases/${caseId}/messages`, signal);
}

/** POST /api/messages/{id}/sent: the worker shared it herself. */
export function markSent(messageId: number, signal?: AbortSignal): Promise<MessageView> {
  return sendJson<MessageView>("POST", `/api/messages/${messageId}/sent`, undefined, signal);
}

// ------------------------------------------------------------------ employer page (public)
export function getEmployerPage(token: string, signal?: AbortSignal): Promise<EmployerPage> {
  return getJson<EmployerPage>(`/api/e/${encodeURIComponent(token)}`, signal);
}

export function markPlayed(
  token: string,
  signal?: AbortSignal,
): Promise<{ ok: boolean; message_id: number | null; status: string | null }> {
  return sendJson("POST", `/api/e/${encodeURIComponent(token)}/played`, undefined, signal);
}

export function pay(token: string, body: PayIn = {}, signal?: AbortSignal): Promise<PayResponse> {
  return sendJson<PayResponse>("POST", `/api/e/${encodeURIComponent(token)}/pay`, body, signal);
}

export function planInstalments(
  token: string,
  body: { instalments: 2 | 3; first_due?: string; every_days?: number },
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return sendJson<PlanResponse>("POST", `/api/e/${encodeURIComponent(token)}/plan`, body, signal);
}

/** POST /api/e/{token}/reply: the employer's voice reply (STT + translation + TTS). */
export function employerReply(
  token: string,
  audio: Blob,
  opts: { lang?: string | null; useLlm?: boolean; filename?: string } = {},
  signal?: AbortSignal,
): Promise<ReplyResponse> {
  const form = new FormData();
  appendAudio(form, audio, opts.filename ?? "reply");
  if (opts.lang) form.append("lang", opts.lang);
  form.append("use_llm", String(opts.useLlm ?? true));
  return sendForm<ReplyResponse>(`/api/e/${encodeURIComponent(token)}/reply`, form, signal);
}

// ------------------------------------------------------------------ voice profile
export function getVoiceProfile(workerId: number, signal?: AbortSignal): Promise<VoiceProfileView> {
  return getJson<VoiceProfileView>(`/api/voice-profile?worker_id=${workerId}`, signal);
}

/** Needs consent=true. 10-20 s of the worker's own voice; only the embedding is stored. */
export function createVoiceProfile(
  workerId: number,
  audio: Blob,
  consent: boolean,
  signal?: AbortSignal,
): Promise<VoiceProfileView> {
  const form = new FormData();
  form.append("worker_id", String(workerId));
  form.append("consent", consent ? "true" : "false");
  appendAudio(form, audio, "voice");
  return sendForm<VoiceProfileView>("/api/voice-profile", form, signal);
}

export function deleteVoiceProfile(workerId: number, signal?: AbortSignal): Promise<VoiceProfileDeleted> {
  return sendJson<VoiceProfileDeleted>("DELETE", `/api/voice-profile?worker_id=${workerId}`, undefined, signal);
}

// ------------------------------------------------------------------ diary
export function listDiary(workerId: number, employerId?: number | null, signal?: AbortSignal): Promise<DiaryList> {
  const q = new URLSearchParams({ worker_id: String(workerId) });
  if (employerId != null) q.set("employer_id", String(employerId));
  return getJson<DiaryList>(`/api/diary?${q}`, signal);
}

/** POST /api/diary: text or voice check-in. Voice without text spends one Gnani STT call. */
export function addDiary(
  body: {
    workerId: number;
    text?: string;
    employerId?: number | null;
    caseId?: number | null;
    kind?: DiaryKind;
    lang?: ListenLang;
    audio?: Blob | null;
  },
  signal?: AbortSignal,
): Promise<DiaryAdded> {
  const form = new FormData();
  form.append("worker_id", String(body.workerId));
  form.append("text", body.text ?? "");
  if (body.employerId != null) form.append("employer_id", String(body.employerId));
  if (body.caseId != null) form.append("case_id", String(body.caseId));
  form.append("kind", body.kind ?? "checkin");
  form.append("lang", body.lang ?? "auto");
  if (body.audio) appendAudio(form, body.audio, "diary");
  return sendForm<DiaryAdded>("/api/diary", form, signal);
}
