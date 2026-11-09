// V12 Case Replay client: GET /api/story/{caseId}. Read-only; every time shown is the stored time.

export type StoryLang = "en" | "te" | "hi";
export type StoryTitle = Record<StoryLang, string>;

export type StoryEvent = {
  seq: number;
  at: string; // stored ISO string, unchanged
  at_field: string; // which column it came from, e.g. "payment.paid_at"
  kind: string;
  title: StoryTitle;
  source_table: string;
  source_id: number | null;
  step?: string;
  text?: string;
  text_worker_lang?: string;
  language?: string;
  amount?: number;
  amount_delta?: number;
  balance_after?: number;
  audio_url?: string;
  original_audio_url?: string;
  pdf_url?: string;
  verified?: boolean;
  due_date?: string;
  hash?: string;
  method?: string;
  note?: string;
  total?: number;
};

export type StoryUntimed = {
  kind: string;
  title: StoryTitle;
  source_table: string;
  source_id: number | null;
  step?: string;
  reason: string;
};

export type Story = {
  case: {
    id: number;
    status: string;
    worker: { name: string; language: string };
    employer: { name: string; language: string; fair_employer: boolean };
    created_at: string;
  };
  total_due: number;
  amount_paid: number;
  balance: number;
  paid_in_full: boolean;
  payments_match_case: boolean;
  events: StoryEvent[];
  untimed: StoryUntimed[];
  skipped: { kind: string; source_table: string; source_id: number | null; reason: string }[];
  notes: string[];
};

export class StoryError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function getStory(caseId: number, signal?: AbortSignal): Promise<Story> {
  const res = await fetch(`/api/story/${caseId}`, { cache: "no-store", signal });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const b = (await res.json()) as { detail?: unknown };
      if (typeof b.detail === "string") msg = b.detail;
    } catch {
      /* not JSON */
    }
    throw new StoryError(msg, res.status);
  }
  return res.json();
}

/** UI language (lib/i18n UiLang) -> the story's title key. */
export function storyLang(ui: string): StoryLang {
  return ui === "te" ? "te" : ui === "hi-en" ? "hi" : "en";
}

const IST = "Asia/Kolkata";

/** The stored time, shown in IST (the stored string itself is in the tooltip). */
export function timeLabel(at: string): { date: string; time: string } {
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return { date: at, time: "" };
  return {
    date: d.toLocaleDateString("en-IN", { timeZone: IST, day: "numeric", month: "short", year: "numeric" }),
    time: d.toLocaleTimeString("en-IN", { timeZone: IST, hour: "2-digit", minute: "2-digit" }),
  };
}

export function rupees(n: number): string {
  return "₹" + Math.round(n).toLocaleString("en-IN");
}
