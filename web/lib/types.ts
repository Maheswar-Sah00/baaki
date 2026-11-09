// Types that mirror the Baaki FastAPI JSON (backend/app/routes/*.py). Keep in step with the backend.
// Money is in rupees (number, may carry paise for estimates). Dates are ISO strings.

/** te-IN = Telugu, hi-en = Hinglish, hi-IN = Hindi, en-IN / en = English. */
export type LangCode = "te-IN" | "hi-en" | "hi-IN" | "en-IN" | "en";
/** Language preset for /listen and /diary. */
export type ListenLang = "auto" | "te" | "hinglish" | "te-IN" | "hi-en";
export type LadderStep = "polite" | "firm" | "formal";
export type CaseStatus = "draft" | "confirmed" | "sent" | "plan" | "paid" | "closed";
export type CardState =
  | "paid"
  | "partly_paid"
  | "below_minimum"
  | "clear"
  | "sent"
  | "ignored"
  | "draft"
  | "confirmed"
  | "plan";

// ------------------------------------------------------------------ people
export type Worker = {
  id: number;
  name: string;
  language: LangCode;
  phone: string | null;
  city: string;
  category: string;
  work_type: string;
  upi_vpa: string | null;
  created_at: string;
};

export type Employer = {
  id: number;
  name: string;
  language: LangCode;
  phone: string | null;
  locality: string | null;
  fair_employer: boolean;
  kaam_patta_signed: boolean;
  created_at: string;
};

// ------------------------------------------------------------------ safety
export type Helpline = { number: string | null; name: string; url?: string; for: string[] };

export type SafetyCategory = { key: string; label: string; matches: string[]; via: "keyword" | "llm" };

export type Safety = {
  flagged: boolean;
  stop_wage_flow: boolean;
  quick_exit: boolean;
  categories: SafetyCategory[];
  helplines: Helpline[];
  message: string | null;
};

// ------------------------------------------------------------------ meter
export type ChipKind =
  | "rate"
  | "cut"
  | "advance"
  | "paid"
  | "stated_total"
  | "owed"
  | "months"
  | "days"
  | "hours";

export type MeterChip = {
  id: string;
  kind: ChipKind;
  value: number;
  label: string;
  label_hint: string | null;
  span: [number, number];
  text: string;
  is_count?: boolean;
  reason?: string;
  per_month?: boolean;
  inferred?: boolean;
};

export type MeterSummary = {
  total: number;
  steps: number[];
  formula: string;
  monthly_wage: number | null;
  months_unpaid: number | null;
  cuts: { amount: number; reason: string | null; days_absent: number | null }[];
  advance: number;
  paid: { amount: number; per_month: boolean }[];
  stated_total: number | null;
  matches_stated_total: boolean | null;
  days: number | null;
  hours_per_day: number | null;
};

export type MeterResponse = MeterSummary & {
  text: string;
  lang: string | null;
  chips: MeterChip[];
  ms?: number;
  safety?: Safety;
};

export type SttChunk = { start_s: number; end_s: number; transcript: string };

export type ListenResponse = {
  transcript: string;
  language_code: string;
  detected_language_code: string | null;
  mode: string;
  duration_s: number;
  chunks: SttChunk[];
  meter: MeterResponse;
  chips: MeterChip[];
  total: number;
  steps: number[];
  safety: Safety;
};

// ------------------------------------------------------------------ facts / calculation
export type Deduction = {
  amount: number;
  reason: string | null;
  days_absent?: number | null;
  month?: string | null;
};

export type Facts = {
  employer_name?: string | null;
  work_type?: string | null;
  hours_per_day?: number | null;
  days_per_week?: number | null;
  monthly_wage?: number | null;
  paid_per_month?: number | null;
  months_unpaid?: number | null;
  unpaid_month_numbers?: number[];
  unpaid_months?: string[];
  paid_months?: Record<string, number>;
  deductions?: Deduction[];
  advance_outstanding?: number | null;
  owed_lumps?: number[];
  stated_total?: number | null;
  dismissed?: boolean;
  dismissed_on?: string | null;
  reasons?: string[];
  include_shortfall?: boolean;
  extraction?: { source: string; warnings: string[] };
  [key: string]: unknown;
};

export type CalcItem = {
  kind: "unpaid_wage" | "illegal_deduction" | "final_settlement" | "min_wage_shortfall" | string;
  label: string;
  month: string | null;
  amount: number;
  is_estimate: boolean;
  included_in_total: boolean;
  due_date: string | null;
  overdue?: boolean;
  days_overdue?: number;
  source: string;
  flag?: string;
  note?: string;
};

export type HaqCheck = {
  minimum_for_hours: number | null;
  agreed: number | null;
  monthly_gap: number | null;
  is_estimate: boolean;
  basis: string;
  source: string;
  needs_hours: boolean;
  per_day_full_time: number;
  full_time_monthly: number;
  vda_note: string;
};

export type Calc = {
  inputs: Record<string, unknown>;
  unpaid_wages: number;
  reclaimable_deductions: number;
  advance_outstanding: number;
  contractual_due: number;
  min_wage_shortfall: number;
  shortfall_is_estimate: boolean;
  total_with_shortfall: number;
  total: number;
  haq_check: HaqCheck | null;
  shortfall_by_month: {
    month: string;
    amount: number;
    is_estimate: boolean;
    source: string;
    basis: string;
    agreed: number;
    gap: number;
  }[];
  deductions: (Deduction & { lawful_max: number; reclaimable: number; flag: string | null; source: string; note: string })[];
  items: CalcItem[];
  due: { settlement_due: string | null; dismissed_on: string | null; earliest_overdue: string | null };
  flags: string[];
  sources: string[];
  disclaimer: string;
};

export type Readback = {
  text: string; // with <slow>/<pauses> tags, for TTS
  plain: string; // for display
  lang: LangCode;
  sentences: string[];
  said_total: number | null;
  legal_total: number | null;
};

export type ReadbackAudio = Readback & {
  audio_url: string | null;
  duration_s: number | null;
  cached: boolean | null;
  tts_error: unknown;
};

export type ExtractResponse = {
  facts: Facts;
  meter: MeterResponse;
  source: "llm" | "parser" | string;
  warnings: string[];
  llm_provider: string | null;
  calc: Calc;
  readback: Readback;
};

// ------------------------------------------------------------------ cases
export type CaseItemRow = {
  id: number;
  case_id: number;
  kind: string;
  label: string;
  month: string | null;
  amount: number;
  is_estimate: boolean;
  included_in_total: boolean;
  due_date: string | null;
  source: string;
  created_at: string;
};

export type PaymentRow = {
  id: number;
  case_id: number;
  amount: number;
  method: string;
  status: "paid" | "planned" | "settled" | string;
  due_date: string | null;
  instalment_no: number | null;
  instalments_total: number | null;
  note: string | null;
  paid_at: string | null;
  created_at: string;
};

export type MessageRow = {
  id: number;
  case_id: number;
  step: string; // polite | firm | formal | reply | paid_alert | reminder | plan
  direction: "to_employer" | "to_worker" | "from_employer";
  language: string;
  text: string;
  text_worker_lang: string | null;
  audio_path: string | null;
  pdf_path: string | null;
  voice_note_id: string | null;
  status: string;
  created_at: string;
  sent_at: string | null;
};

export type CaseDetail = {
  id: number;
  status: CaseStatus;
  worker: Worker | null;
  employer: Employer | null;
  work_type: string;
  category: string;
  monthly_wage: number;
  hours_per_day: number;
  days_per_week: number;
  months_unpaid: number;
  dismissed: boolean;
  end_date: string | null;
  transcript: string;
  transcript_lang: string;
  facts: Facts;
  calc: Calc;
  safety: Partial<Safety>;
  total_due: number;
  shortfall_estimate: number;
  amount_paid: number;
  balance: number;
  items: CaseItemRow[];
  payments: PaymentRow[];
  messages: MessageRow[];
  employer_token: string;
  employer_path: string;
  readback: Readback;
  readback_confirmed: boolean;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type EmployerIn = { name: string; language?: LangCode; phone?: string | null; locality?: string | null };

export type CaseCreate = {
  worker_id: number;
  employer_id?: number | null;
  employer?: EmployerIn | null;
  transcript?: string;
  lang?: string | null;
  facts?: Facts | null;
  include_shortfall?: boolean;
  use_llm?: boolean;
};

// ------------------------------------------------------------------ dashboard
export type DashboardCard = {
  case_id: number;
  employer: Employer | null;
  fair_employer: boolean;
  status: CaseStatus;
  state: CardState;
  total_due: number;
  amount_paid: number;
  balance: number;
  shortfall_estimate: number;
  haq_check: HaqCheck | null;
  monthly_wage: number;
  hours_per_day: number;
  months_unpaid: number;
  last_step: string | null;
  last_sent_at: string | null;
  next_reminder: string | null;
  employer_path: string;
  earliest_overdue: string | null;
};

export type Dashboard = {
  worker: Worker;
  cards: DashboardCard[];
  totals: { homes: number; baaki: number; recovered: number; hidden_baaki_estimate: number };
};

export type DemoReset = {
  today: string;
  workers: Record<string, number>;
  employers: Record<string, number>;
  cases: Record<string, number>;
  employer_tokens: Record<string, string>;
  totals: Record<string, number>;
};

// ------------------------------------------------------------------ messages (ladder)
export type MessageView = {
  message_id: number;
  case_id: number;
  step: string;
  direction: string;
  language: string;
  text: string;
  text_worker_lang: string | null;
  audio_url: string | null;
  pdf_url: string | null;
  voice_note_id: string | null;
  status: string;
  created_at: string;
  sent_at: string | null;
  employer_url?: string;
};

export type GnaniErrorInfo = { source?: string; message?: string; status?: number; [k: string]: unknown };

export type StepResponse = MessageView & {
  reused: boolean;
  source?: string;
  sentences?: string[];
  speech?: string[];
  disclosure?: string;
  reply_by?: string;
  voice_mode: "clone" | "stock";
  audio?: {
    url: string;
    duration_s: number;
    voice_mode: string;
    voice: string;
    voice_note_id: string;
    gnani_calls: number;
    cache_hits: number;
    sentences: number;
    metadata_comment: string;
  } | null;
  audio_error?: GnaniErrorInfo | null;
  upi_link: string | null;
  share_text?: string;
  balance: number;
  checks?: unknown;
};

export type StepOptions = {
  use_llm?: boolean;
  regenerate?: boolean;
  voice?: "auto" | "stock" | "clone";
  audio?: boolean;
  pdf?: boolean;
  lang?: string | null;
};

// ------------------------------------------------------------------ employer page
export type EmployerItem = {
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

export type Badge = {
  title: string;
  reason: "paid_in_full" | "kaam_patta";
  employer: string;
  text: string;
  text_en: string;
  share_text: string;
};

export type PlanRow = {
  payment_id: number;
  instalment_no: number;
  instalments_total: number;
  amount: number;
  due_date: string | null;
  status: string;
};

export type EmployerPage = {
  case_id: number;
  status: CaseStatus;
  worker: { name: string; language: LangCode };
  employer: { name: string; language: LangCode; fair_employer: boolean };
  items: EmployerItem[];
  total_due: number;
  amount_paid: number;
  balance: number;
  balance_display: string;
  currency: "INR";
  message: MessageView | null;
  audio_url: string | null;
  pdf_url: string | null;
  upi: { vpa: string; link: string } | null;
  plan: PlanRow[];
  replies: MessageView[];
  badge: Badge | null;
  ai_notice: string;
};

export type PayIn = { amount?: number; method?: "upi" | "cash" | "bank" | "other"; note?: string; alert_audio?: boolean };

export type PayResponse = {
  paid: number;
  paid_display: string;
  amount_paid: number;
  balance: number;
  status: CaseStatus;
  fully_paid: boolean;
  fair_employer: boolean;
  badge: Badge | null;
  alert: {
    message_id: number;
    text: string;
    speech: string;
    language: string;
    audio: { url: string; duration_s: number; voice: string; voice_note_id: string; gnani_calls: number } | null;
    audio_error: GnaniErrorInfo | null;
  };
};

export type PlanResponse = {
  case_id: number;
  status: "plan";
  balance: number;
  instalments: {
    payment_id: number;
    instalment_no: number;
    amount: number;
    amount_display: string;
    due_date: string;
    status: string;
    reminder: { message_id: number; text: string; send_on: string; status: string };
    upi_link: string | null;
  }[];
  total_check: boolean;
  worker_note: { message_id: number; text: string };
};

export type ReplyResponse = {
  transcript: string;
  language: string;
  stt: { language_code: string | null; mode: string | null; duration_s: number | null };
  amounts: { value: number; text: string; start: number; end: number }[];
  translation: { text: string; language: string; source: string; speech: string[]; amounts: unknown; checks: unknown };
  audio: { url: string; duration_s: number; voice: string; voice_note_id: string } | null;
  audio_error: GnaniErrorInfo | null;
  original_audio_url: string | null;
  message_ids: { from_employer: number; to_worker: number };
  employer_url: string;
};

// ------------------------------------------------------------------ voice profile
export type VoiceProfileView = {
  exists: boolean;
  consent_text: string;
  default_voice: string;
  profile_id?: number;
  worker_id?: number;
  consent?: boolean;
  consent_at?: string | null;
  model?: string | null;
  duration_s?: number | null;
  embedding_shape?: unknown;
  stored?: string;
  audio_stored?: boolean;
  trimmed_to_20s?: boolean;
};

export type VoiceProfileDeleted = { worker_id: number; deleted: number; exists: false; voice: string };

// ------------------------------------------------------------------ diary
export type DiaryKind = "checkin" | "absence" | "payment" | "note";

export type DiaryEntry = {
  id: number;
  worker_id: number;
  employer_id: number | null;
  case_id: number | null;
  timestamp: string;
  kind: DiaryKind;
  text: string;
  audio_sha256: string | null;
  prev_hash: string;
  hash: string;
};

export type DiaryChain = { valid: boolean; broken_at: number | null; head: string | null; count: number };

export type DiaryList = { entries: DiaryEntry[]; chain: DiaryChain };

export type DiaryAdded = { entry: DiaryEntry; hours: number | null };

export type Health = { ok: boolean; gnani: boolean; llm: boolean; llm_provider: string };
