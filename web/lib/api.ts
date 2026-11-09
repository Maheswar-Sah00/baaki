// Typed client for the FastAPI backend. Every call goes to the same origin (/api/*), which
// Next rewrites to the backend (next.config.ts). No API keys ever live in the browser.
// Adapted from Deposit Wapas web/lib/api.ts (generic parts only).

export type SttChunk = { start_s: number; end_s: number; transcript: string };

export type SttResponse = {
  transcript: string;
  detected_language_code: string | null;
  language_code: string;
  mode: string;
  chunks: SttChunk[];
  duration_s: number;
  model: string;
};

/** te = Telugu, hinglish = Hindi/Hinglish code-mix, auto = either (default). */
export type SttLang = "te" | "hinglish" | "auto" | "indic-auto";
export type SttMode = "transcribe" | "codemix" | "verbatim" | "transliterate";

/** hi-en = Hinglish. */
export type TtsLang = "te-IN" | "hi-IN" | "hi-en" | "en-IN";
export type TtsModel = "timbre-v3.0" | "timbre-v2.5";
export type TtsFormat = "ogg" | "mp3";

export type Health = { ok: boolean; gnani: boolean; llm: boolean; llm_provider: string };

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function ensureOk(res: Response): Promise<Response> {
  if (res.ok) return res;
  let message = `${res.status} ${res.statusText || "error"}`.trim();
  let body: unknown = null;
  try {
    const text = await res.text();
    if (text) {
      try {
        body = JSON.parse(text);
        const o = body as { detail?: unknown; error?: unknown; message?: unknown };
        const detail = o?.detail ?? o?.error ?? o?.message;
        if (typeof detail === "string") message = `${res.status}: ${detail}`;
        else if (detail !== undefined) message = `${res.status}: ${JSON.stringify(detail).slice(0, 300)}`;
        else message = `${res.status}: ${text.slice(0, 300)}`;
      } catch {
        message = `${res.status}: ${text.slice(0, 300)}`;
      }
    }
  } catch {
    /* keep the fallback message */
  }
  throw new ApiError(message, res.status, body);
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 502 || err.status === 503 || err.status === 504) {
      return `The server is busy or waking up (${err.status}). Try again in a moment.`;
    }
    if (err.status === 500 && /^500: Internal Server Error\s*$/i.test(err.message)) {
      return "The server is not answering. Is the backend running?";
    }
    return err.message;
  }
  if (err instanceof TypeError) return "No connection to the server. Check the internet and try again.";
  if (err instanceof Error) return err.message;
  return String(err);
}

function now(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
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

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const res = await ensureOk(await fetch("/api/health", { cache: "no-store", signal }));
  return (await res.json()) as Health;
}

export async function postStt(
  audio: Blob,
  filename: string,
  opts: { lang?: SttLang | string; mode?: SttMode } = {},
  signal?: AbortSignal,
): Promise<{ data: SttResponse; ms: number }> {
  const form = new FormData();
  form.append("audio", audio, audioUploadName(filename, audio.type));
  if (opts.lang) form.append("lang", opts.lang);
  if (opts.mode) form.append("mode", opts.mode);
  const t0 = now();
  const res = await ensureOk(await fetch("/api/stt", { method: "POST", body: form, signal }));
  return { data: (await res.json()) as SttResponse, ms: Math.round(now() - t0) };
}

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
