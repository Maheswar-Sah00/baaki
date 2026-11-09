// Noise proof (G04+V14): types and fetch for GET /api/proof, plus transcript highlighting.
// Read-only page data; the backend never calls Gnani for this route.

export type ProofSpan = { start: number; end: number; amount: number; text: string; match: boolean };
export type ProofSlip = { said: string; heard: string };

export type ProofClip = {
  clip_id: string;
  utt_id: string;
  lang: "te" | "hinglish";
  lang_label: string;
  voice: string;
  condition: string;
  condition_label: string;
  snr_db: number | null;
  text: string;
  gloss: string;
  expected: number[];
  heard: number[];
  amounts: { amount: number; heard: boolean }[];
  hits: number;
  total: number;
  extras: number[];
  spans: ProofSpan[];
  match: boolean;
  word_slips: ProofSlip[];
  transcript: string | null;
  latency_s: number | null;
  duration_s: number | null;
  sample_rate: number | null;
  stt_language_code: string | null;
  mode: string | null;
  model: string | null;
  error: string | null;
  audio_url: string;
  clean_url: string;
};

export type ProofCondition = {
  condition: string;
  label: string;
  short: string;
  desc: string;
  snr_db: number | null;
  clips: number;
  clips_exact: number;
  amounts: number;
  exact: number;
  rate: number | null;
  extras: number;
  by_lang: Record<string, { exact: number; amounts: number }>;
  median_latency_s: number | null;
};

export type ProofMiss = {
  clip_id: string;
  utt_id: string;
  condition: string;
  lang: string;
  missed: number[];
  extras: number[];
  transcript: string;
};

export type ProofSummary = {
  headline: {
    exact: number;
    amounts: number;
    clips: number;
    rate: number | null;
    conditions: string[];
    text: string;
    hardest: { condition: string; exact: number; amounts: number; text: string } | null;
  } | null;
  per_condition: ProofCondition[];
  overall: { clips: number; amounts: number; exact: number; rate: number | null };
  noisy: { clips: number; amounts: number; exact: number; rate: number | null };
  misses: ProofMiss[];
  word_slips: number;
  clips_with_word_slips: number;
};

export type ProofData = {
  available: boolean;
  generated_at?: string | null;
  run_dates?: string[];
  model?: string;
  calls?: { tts: number | null; stt: number | null };
  summary: ProofSummary | null;
  conditions?: { id: string; label: string; short: string; desc: string; snr_db: number | null }[];
  method: string[];
  caveats: string[];
  clips: ProofClip[];
};

export async function fetchProof(signal?: AbortSignal): Promise<ProofData> {
  const r = await fetch("/api/proof", { signal, headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`proof ${r.status}`);
  return (await r.json()) as ProofData;
}

/** Split a transcript into plain and amount pieces (spans index into the transcript string). */
export function segments(text: string, spans: ProofSpan[]): { text: string; span?: ProofSpan }[] {
  const out: { text: string; span?: ProofSpan }[] = [];
  let at = 0;
  for (const s of [...spans].sort((a, b) => a.start - b.start)) {
    if (s.start < at || s.end > text.length) continue;
    if (s.start > at) out.push({ text: text.slice(at, s.start) });
    out.push({ text: text.slice(s.start, s.end), span: s });
    at = s.end;
  }
  if (at < text.length) out.push({ text: text.slice(at) });
  return out;
}

/** Clips grouped by sentence, in corpus order, conditions in bench order. */
export function bySentence(clips: ProofClip[]): { utt_id: string; rows: ProofClip[] }[] {
  const map = new Map<string, ProofClip[]>();
  for (const c of clips) {
    if (!map.has(c.utt_id)) map.set(c.utt_id, []);
    map.get(c.utt_id)!.push(c);
  }
  const order = (id: string) => (id.startsWith("te") ? 0 : 1) * 100 + Number(id.slice(2));
  return [...map.entries()].sort((a, b) => order(a[0]) - order(b[0])).map(([utt_id, rows]) => ({ utt_id, rows }));
}

export function inrPlain(n: number): string {
  return "₹" + n.toLocaleString("en-IN");
}

export function runDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
}
