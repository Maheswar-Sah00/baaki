// V04 "Be Sharma ji" client: typed calls to /api/sandbox*. A public, synthetic employer sandbox with
// cached audio only (no live AI calls, no real money). The browser remembers only the sandbox id.

export const SANDBOX_BANNER = "Synthetic demo. Lakshmi is fictional.";

export type SandboxMeta = {
  sandbox_id: string;
  banner: string;
  synthetic: true;
  expires_at: string;
  expires_in_s: number;
};

export type SandboxItem = {
  id: number;
  kind: string;
  label: string;
  label_en: string;
  month: string | null;
  amount: number;
  amount_display: string;
  due_date: string | null;
  is_estimate: boolean;
  included_in_total: boolean;
  source: string;
};

export type SandboxBadge = { title: string; reason: string; employer: string; text: string; text_en: string; share_text: string };

export type SandboxAlert = {
  headline: string;
  headline_en: string;
  text: string;
  language: string;
  sent_at: string | null;
  audio_url: string | null;
  audio_label: string;
};

export type SandboxView = SandboxMeta & {
  status: string;
  worker: { name: string; language: string };
  employer: { name: string; language: string; fair_employer: boolean };
  items: SandboxItem[];
  total_due: number;
  amount_paid: number;
  balance: number;
  balance_display: string;
  currency: "INR";
  message: { text: string | null; language: string | null; status: string | null; sent_at: string | null } | null;
  voice_note: { available: boolean; audio_url: string | null; label: string; reason: string | null };
  upi: { enabled: false; label: string };
  reply: { enabled: false; label: string };
  badge: SandboxBadge | null;
  played: boolean;
  paid: boolean;
  ai_notice: string;
  ttl_s?: number;
};

export type SandboxPaid = SandboxMeta & {
  already_paid: boolean;
  paid: number | null;
  paid_display: string | null;
  amount_paid: number;
  balance: number;
  balance_display: string;
  fully_paid: boolean;
  status: string;
  badge: SandboxBadge | null;
  note: string;
  alert: SandboxAlert | null;
};

export type SandboxWorker = SandboxMeta & {
  worker: { name: string; language: string };
  employer: { name: string; fair_employer: boolean };
  status: string;
  total_due: number;
  amount_paid: number;
  balance: number;
  balance_display: string;
  note_status: string | null;
  played: boolean;
  paid: boolean;
  alert: SandboxAlert | null;
};

export class SandboxError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) {
    super(message);
  }
  get gone(): boolean {
    return this.status === 404 || this.status === 410;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { cache: "no-store", ...init });
  } catch {
    throw new SandboxError(0, "network", "Could not reach Baaki. Check your connection.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new SandboxError(res.status, body?.error ?? "error", body?.message ?? `Request failed (${res.status})`,
      body?.retry_after_s);
  }
  return body as T;
}

export const createSandbox = () => call<SandboxView>("/api/sandbox", { method: "POST" });
export const getSandbox = (sid: string) => call<SandboxView>(`/api/sandbox/${encodeURIComponent(sid)}`);
export const markPlayed = (sid: string) =>
  call<SandboxMeta & { played: boolean }>(`/api/sandbox/${encodeURIComponent(sid)}/played`, { method: "POST" });
export const markPaid = (sid: string) =>
  call<SandboxPaid>(`/api/sandbox/${encodeURIComponent(sid)}/paid`, { method: "POST" });
export const getWorkerPanel = (sid: string) =>
  call<SandboxWorker>(`/api/sandbox/${encodeURIComponent(sid)}/worker`);

const KEY = "baaki.sandbox.sid";

export function rememberedSid(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function rememberSid(sid: string | null): void {
  try {
    if (sid) localStorage.setItem(KEY, sid);
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode: the sandbox still works for this visit */
  }
}

/** Reuse this browser's live sandbox if it has one, else start a new one. */
export async function openSandbox(fresh = false): Promise<SandboxView> {
  const sid = fresh ? null : rememberedSid();
  if (sid) {
    try {
      return await getSandbox(sid);
    } catch (e) {
      if (!(e instanceof SandboxError && e.gone)) throw e;
    }
  }
  const view = await createSandbox();
  rememberSid(view.sandbox_id);
  return view;
}
