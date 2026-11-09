// Listen-twice guard (G07): Prisma re-hears the voice note before the worker shares it.
// Backend: backend/app/routes/verify.py. The result only warns; sending is never blocked.

export type VerifyResult = {
  message_id: number;
  step: string;
  verified: boolean;
  amounts_ok: boolean;
  amounts_expected: number[];
  amounts_heard: number[];
  missing: number[];
  extra: number[];
  total_expected: number | null;
  total_heard: boolean;
  disclosure_heard: boolean;
  disclosure_score: number;
  ai_word_heard: boolean;
  transcript: string;
  language_code: string | null;
  stt_mode: string | null;
  stt_calls: number;
  ms: number;
  audio_sha256: string;
  cached: boolean;
  checked_at?: string;
};

export class VerifyError extends Error {
  status: number;
  code: string | null;
  constructor(message: string, status: number, code: string | null) {
    super(message);
    this.name = "VerifyError";
    this.status = status;
    this.code = code;
  }
}

async function call(method: "GET" | "POST", messageId: number, force: boolean, signal?: AbortSignal): Promise<VerifyResult> {
  const q = force ? "?force=true" : "";
  const res = await fetch(`/api/verify/messages/${messageId}${q}`, { method, cache: "no-store", signal });
  if (!res.ok) {
    let code: string | null = null;
    let message = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: { error?: string; message?: string } | string };
      if (body?.detail && typeof body.detail === "object") {
        code = body.detail.error ?? null;
        message = body.detail.message ?? message;
      } else if (typeof body?.detail === "string") {
        message = body.detail;
      }
    } catch {
      /* keep the status */
    }
    throw new VerifyError(message, res.status, code);
  }
  return (await res.json()) as VerifyResult;
}

/** The cached result for the message's current audio, or null when it has not been checked. */
export async function getVerify(messageId: number, signal?: AbortSignal): Promise<VerifyResult | null> {
  try {
    return await call("GET", messageId, false, signal);
  } catch (e) {
    if (e instanceof VerifyError && e.status === 404 && e.code === "not_checked") return null;
    throw e;
  }
}

/** Run the check (Prisma STT, cached per audio hash, so a repeat costs nothing). */
export function runVerify(messageId: number, opts: { force?: boolean; signal?: AbortSignal } = {}): Promise<VerifyResult> {
  return call("POST", messageId, Boolean(opts.force), opts.signal);
}

/** Cached result if there is one, otherwise run the check. */
export async function verifyMessage(messageId: number, signal?: AbortSignal): Promise<VerifyResult> {
  return (await getVerify(messageId, signal)) ?? (await runVerify(messageId, { signal }));
}
