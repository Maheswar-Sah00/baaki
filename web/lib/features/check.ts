// Fair Pay Check (V01) client: typed calls to /api/check*, plus the payday-reminder links.
// Nothing is stored server-side; the browser only remembers the chosen UI language.

export type WorkType = "maid" | "cooking" | "both" | "care";

export type CheckInput = {
  work_type: WorkType;
  hours_per_day: number;
  days_per_week: number;
  monthly_pay: number;
};

export type CheckResult = {
  work_type: WorkType;
  work_label: string;
  category: string;
  category_label: string;
  order_line: string;
  month: string;
  hours_per_day: number;
  days_per_week: number;
  working_days_per_month: number;
  monthly_pay: number;
  minimum_monthly: number;
  full_time_monthly: number;
  per_hour_estimate: number;
  is_estimate: boolean;
  basis: string;
  how: string;
  gap_monthly: number;
  gap_yearly: number;
  per_day_to_close: number;
  verdict: "fair" | "below";
  alt_rate: { category: string; label: string; minimum_monthly: number; gap_monthly: number } | null;
  explanation: string;
  notes: string[];
  source: string;
  source_url: string;
  disclaimer: string;
};

export type Parsed = {
  work_type: WorkType | null;
  hours_per_day: number | null;
  days_per_week: number | null;
  monthly_pay: number | null;
  missing: string[];
};

export type SpeakOk = { parsed: Parsed; result: CheckResult | null; transcript: string; remaining_today: number };
export type SpeakFallback = { error: string; message: string; fallback: "tap"; remaining_today: number };

export class CheckError extends Error {
  status: number;
  code: string | null;
  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function readError(res: Response): Promise<CheckError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* not JSON */
  }
  const b = (body ?? {}) as { error?: string; message?: string; detail?: unknown };
  const msg = b.message ?? (typeof b.detail === "string" ? b.detail : `Request failed (${res.status})`);
  return new CheckError(msg, res.status, b.error ?? null);
}

export async function runCheck(input: CheckInput, signal?: AbortSignal): Promise<CheckResult> {
  const res = await fetch("/api/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    signal,
    cache: "no-store",
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function speakCheck(blob: Blob, filename: string, workType?: WorkType | null): Promise<SpeakOk> {
  const fd = new FormData();
  fd.append("audio", blob, filename);
  if (workType) fd.append("work_type", workType);
  const res = await fetch("/api/check/speak", { method: "POST", body: fd, cache: "no-store" });
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function speakQuota(): Promise<number> {
  try {
    const res = await fetch("/api/check/speak/quota", { cache: "no-store" });
    if (!res.ok) return 0;
    return ((await res.json()) as { remaining_today: number }).remaining_today;
  } catch {
    return 0;
  }
}

// ------------------------------------------------------------------ payday reminder
const pad = (n: number) => String(n).padStart(2, "0");
const ymd = (d: Date) => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;

/** The 1st of next month: pay is due before the 7th (Code on Wages s.17(1)(iv)), so remind early. */
export function nextReminderDate(now = new Date()): Date {
  return new Date(now.getFullYear(), now.getMonth() + 1, 1);
}

export function googleCalendarUrl(title: string, details: string, now = new Date()): string {
  const start = nextReminderDate(now);
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1);
  const q = new URLSearchParams({
    action: "TEMPLATE",
    text: title,
    details,
    dates: `${ymd(start)}/${ymd(end)}`,
    recur: "RRULE:FREQ=MONTHLY",
  });
  return `https://calendar.google.com/calendar/render?${q.toString()}`;
}

export function icsFile(title: string, details: string, now = new Date()): Blob {
  const start = nextReminderDate(now);
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1);
  const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Baaki//Fair Pay Check//EN",
    "BEGIN:VEVENT",
    `UID:payday-${stamp}@baaki`,
    `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${ymd(start)}`,
    `DTEND;VALUE=DATE:${ymd(end)}`,
    "RRULE:FREQ=MONTHLY",
    `SUMMARY:${esc(title)}`,
    `DESCRIPTION:${esc(details)}`,
    "BEGIN:VALARM",
    "TRIGGER:PT9H",
    "ACTION:DISPLAY",
    `DESCRIPTION:${esc(title)}`,
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return new Blob([lines.join("\r\n")], { type: "text/calendar" });
}
