"use client";

// /raise/[caseId]: Haq Raise, the worker side. Hero: her pay vs the legal estimate and "₹18,000 more every year".
// She picks a plan (full now, or a step-up), optionally says a line in her own words, and Baaki writes a warm
// request in the EMPLOYER's language with a voice note (AI disclosure first). The law is OFF by default (judge J1).
// She shares it herself. When the employer accepts, this screen celebrates in her language.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BottomSheet,
  Card,
  Confetti,
  CountUp,
  ErrorNote,
  GradientButton,
  Illustration,
  Loading,
  MicButton,
  PlayButton,
  Screen,
  SkeletonCard,
  StatusPill,
  Toggle,
  type PillTone,
} from "@/components/ui/primitives";
import { FileIcon, ShareIcon, SparkIcon } from "@/components/ui/icons";
import { useAudioPlayer, useListen, usePressToTalk, useT } from "@/hooks";
import { monthLabel } from "@/lib/format";
import { fileFromUrl, shareMessage } from "@/lib/share";
import type { ListenLang } from "@/lib/types";
import {
  HTML_LANG,
  isAnswered,
  media,
  raiseApi,
  raiseError,
  raiseLangOf,
  raiseLink,
  rupees,
  type Celebration,
  type ComposeBody,
  type RaiseCaseView,
  type RaiseLang,
  type RaisePlan,
  type RaiseStatus,
  type RaiseView,
} from "@/lib/features/raise";
import { workerStrings, type WorkerStrings } from "./strings";
import css from "./raise.module.css";

const LISTEN_LANG: Record<RaiseLang, ListenLang> = { "te-IN": "te", "hi-en": "hinglish", en: "auto" };
const POLL_MS = 4000;

function seenKey(id: number) {
  return `baaki-raise-celebrated-${id}`;
}
function wasSeen(id: number): boolean {
  try {
    return window.localStorage.getItem(seenKey(id)) === "1";
  } catch {
    return false;
  }
}
function markSeen(id: number) {
  try {
    window.localStorage.setItem(seenKey(id), "1");
  } catch {
    /* private mode: it may show again, which is fine */
  }
}

function statusTone(s: RaiseStatus): PillTone {
  if (s === "accepted" || s === "stepped") return "success";
  if (s === "talk") return "warn";
  if (s === "sent" || s === "played") return "live";
  return "accent";
}

type Custom = { step1: number | null; ask: number | null; months: number | null };

export function RaiseWorkerScreen({ caseId }: { caseId: number }) {
  const { t, lang } = useT();
  const rl = raiseLangOf(lang);
  const S = workerStrings(rl);
  const [v, setV] = useState<RaiseCaseView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<RaisePlan>("step");
  const [custom, setCustom] = useState<Custom>({ step1: null, ask: null, months: null });
  const [years, setYears] = useState("");
  const [mentionLaw, setMentionLaw] = useState(false);
  const [personal, setPersonal] = useState<{ text: string; lang: RaiseLang } | null>(null);
  const [busy, setBusy] = useState(false);
  const [composeError, setComposeError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [celebrate, setCelebrate] = useState<Celebration | null>(null);
  const fileRef = useRef<File | null>(null);
  const inited = useRef(false);
  const player = useAudioPlayer();

  const applyView = useCallback((view: RaiseCaseView) => {
    setV(view);
    const r = view.raise;
    if (!inited.current) {
      inited.current = true;
      if (r) {
        setPlan(r.plan);
        setMentionLaw(r.mention_law);
        if (r.years_worked) setYears(String(r.years_worked));
        if (r.plan === "step") setCustom({ step1: r.step1_amount, ask: r.ask_amount, months: r.step_months });
        else setCustom({ step1: null, ask: r.ask_amount, months: null });
      } else if (!view.plans.step) {
        setPlan("full");
      }
    }
    const c = r?.celebration;
    if (c && isAnswered(r?.status) && !wasSeen(c.event_id)) setCelebrate(c);
  }, []);

  const load = useCallback(
    async (signal?: AbortSignal, quiet = false) => {
      try {
        applyView(await raiseApi.caseView(caseId, signal));
        setError(null);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        if (!quiet) setError(raiseError(e));
      } finally {
        setLoading(false);
      }
    },
    [caseId, applyView],
  );

  useEffect(() => {
    const ac = new AbortController();
    // load() sets state only after its fetch resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(ac.signal);
    return () => ac.abort();
  }, [load]);

  // Waiting for the employer: poll so the celebration lands on her screen by itself.
  const status = v?.raise?.status;
  useEffect(() => {
    if (!status || status === "draft" || isAnswered(status)) return;
    const id = window.setInterval(() => void load(undefined, true), POLL_MS);
    return () => window.clearInterval(id);
  }, [status, load]);

  // Play the celebration once it opens (a blocked autoplay shows the play button instead).
  useEffect(() => {
    if (celebrate?.audio_url) void player.play(media(celebrate.audio_url));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [celebrate?.event_id]);

  const workerLang: RaiseLang = v?.worker.language ?? rl;
  const listen = useListen({
    lang: LISTEN_LANG[workerLang],
    useLlm: false,
    maxMs: 30_000,
    onResult: (r, info) => {
      if (info.final && r.transcript.trim()) setPersonal({ text: r.transcript.trim(), lang: workerLang });
    },
  });
  const ptt = usePressToTalk(listen.recorder, { disabled: busy });

  const n = v?.numbers;
  const base = v ? v.plans[plan] ?? v.plans.full : null;
  const ask = custom.ask ?? base?.ask ?? n?.target ?? 0;
  const step1 = custom.step1 ?? v?.plans.step?.step1 ?? null;
  const months = custom.months ?? v?.plans.step?.months ?? 6;
  const startLabel = v?.plans.full?.start_display ?? "";
  const employerName = v ? v.employer.name_by_lang?.[rl] || v.employer.name_display : "";

  const compose = useCallback(async () => {
    if (!v) return;
    setBusy(true);
    setComposeError(null);
    setNote(null);
    const body: ComposeBody = {
      plan,
      ask_amount: custom.ask ?? undefined,
      step1_amount: plan === "step" ? custom.step1 ?? undefined : undefined,
      step_months: plan === "step" ? custom.months ?? undefined : undefined,
      mention_law: mentionLaw,
      years_worked: years ? Number(years) : null,
      personal_text: personal?.text ?? null,
      personal_lang: personal?.lang ?? null,
      use_llm: true,
      audio: true,
    };
    try {
      const r = await raiseApi.compose(caseId, body);
      setV((prev) => (prev ? { ...prev, raise: r } : prev));
      setEditing(false);
      fileRef.current = null;
      const url = media(r.audio_url);
      if (url) {
        fileFromUrl(url, "raise-request.ogg")
          .then((f) => {
            fileRef.current = f;
          })
          .catch(() => undefined);
      }
    } catch (e) {
      setComposeError(raiseError(e));
    } finally {
      setBusy(false);
    }
  }, [v, plan, custom, mentionLaw, years, personal, caseId]);

  const send = useCallback(async () => {
    const r = v?.raise;
    if (!r?.message.text) return;
    const result = await shareMessage({
      text: r.message.text,
      url: raiseLink(r.employer_path),
      title: S.title,
      file: fileRef.current,
    });
    if (result === "cancelled" || result === "failed") return;
    if (result === "copied") setNote(S.copied);
    try {
      await raiseApi.sent(caseId);
      await load(undefined, true);
    } catch {
      /* the share went out; the status will catch up */
    }
  }, [v, caseId, load, S.title, S.copied]);

  const closeCelebration = () => {
    if (celebrate) markSeen(celebrate.event_id);
    player.stop();
    setCelebrate(null);
  };

  const r = v?.raise ?? null;
  const showForm = v && n && n.gap_monthly > 0 && (!r || (editing && !isAnswered(r.status)));

  return (
    <Screen title={S.title} back={`/case/${caseId}`} t={t}>
      {loading && !v ? (
        <div role="status" aria-label={S.loading} className="stack">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : null}
      {!v && !loading ? <ErrorNote message={error ?? S.error} onRetry={() => void load()} retryLabel={S.retry} /> : null}

      {v && n ? (
        <>
          <Hero v={v} S={S} lang={lang} />

          {n.gap_monthly <= 0 && !r ? (
            <Card tone="soft">
              <p style={{ margin: 0 }}>{S.noGap}</p>
            </Card>
          ) : null}

          {showForm ? (
            <>
              <section className={`${css.section} ${css.rise}`} aria-label={S.pickPlan}>
                <h2 className="section-title">{S.pickPlan}</h2>
                <div className={css.choices} role="radiogroup" aria-label={S.pickPlan}>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={plan === "full"}
                    className={css.choice}
                    onClick={() => setPlan("full")}
                  >
                    <span className={css.radio} aria-hidden="true" />
                    <span>
                      <p className={css.choiceTitle}>{S.planFull}</p>
                      <p className={css.choiceLine}>{S.planFullLine(rupees(ask), startLabel)}</p>
                    </span>
                    <span />
                  </button>
                  {v.plans.step ? (
                    <div
                      role="radio"
                      aria-checked={plan === "step"}
                      tabIndex={0}
                      className={css.choice}
                      onClick={() => setPlan("step")}
                      onKeyDown={(e) => {
                        if (e.key === " " || e.key === "Enter") {
                          e.preventDefault();
                          setPlan("step");
                        }
                      }}
                    >
                      <span className={css.radio} aria-hidden="true" />
                      <span>
                        <p className={css.choiceTitle}>{S.planStep}</p>
                        <p className={css.choiceLine}>{S.planStepLine(rupees(step1), rupees(ask), months)}</p>
                      </span>
                      <button
                        type="button"
                        className={css.editBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          setPlan("step");
                          setEditOpen(true);
                        }}
                      >
                        {S.edit}
                      </button>
                    </div>
                  ) : null}
                </div>
              </section>

              <Card className={css.rise}>
                <div className={css.section}>
                  <label className={css.field}>
                    <span className="field-label">{S.years}</span>
                    <input
                      className={css.input}
                      type="number"
                      inputMode="numeric"
                      min={0}
                      max={60}
                      value={years}
                      onChange={(e) => setYears(e.target.value)}
                    />
                    <span className={css.hint}>{S.yearsHint}</span>
                  </label>
                  <div className={css.lawBox}>
                    <Toggle checked={mentionLaw} onChange={setMentionLaw} label={S.lawToggle} />
                    <p className={css.hint}>{S.lawHint}</p>
                  </div>
                </div>
              </Card>

              <Card className={css.rise}>
                <div className={css.personal}>
                  <p className="field-label" style={{ justifySelf: "start" }}>
                    {S.personal}
                  </p>
                  {personal ? (
                    <>
                      <p className={css.quote} lang={HTML_LANG[personal.lang]}>
                        “{personal.text}”
                      </p>
                      <button type="button" className="btn btn-ghost btn-small" onClick={() => setPersonal(null)}>
                        {S.remove}
                      </button>
                    </>
                  ) : (
                    <MicButton
                      state={listen.status === "listening" ? "starting" : listen.recorder.state}
                      level={listen.level}
                      elapsedMs={listen.elapsedMs}
                      disabled={busy || listen.status === "listening"}
                      handlers={ptt}
                      label={listen.status === "listening" ? S.listening : S.tapToSpeak}
                      size="small"
                    />
                  )}
                  {listen.error ? <p className={css.hint}>{listen.error}</p> : null}
                  <p className={css.hint} style={{ justifySelf: "start" }}>
                    {S.personalHint}
                  </p>
                </div>
              </Card>

              <ErrorNote message={composeError} />
              {busy ? <Loading label={S.making} /> : null}
              <GradientButton onClick={() => void compose()} disabled={busy} icon={<SparkIcon />}>
                {S.make}
              </GradientButton>
            </>
          ) : null}

          {r && !showForm ? (
            <MessageCard
              r={r}
              S={S}
              employer={employerName}
              uiLang={lang}
              player={player}
              note={note}
              onSend={() => void send()}
              onEdit={() => setEditing(true)}
            />
          ) : null}

          <p className="footnote">{S.notAdvice}</p>

          <BottomSheet open={editOpen} onClose={() => setEditOpen(false)} title={S.editTitle} closeLabel={S.ok}>
            <EditForm
              S={S}
              initial={{ step1: step1 ?? 0, ask, months }}
              current={n.current}
              onSave={(c) => {
                setCustom(c);
                setEditOpen(false);
              }}
            />
          </BottomSheet>
        </>
      ) : null}

      {celebrate ? (
        <div className="celebrate" role="dialog" aria-modal="true" aria-labelledby="raise-cel-title">
          <span className="celebrate-rays" aria-hidden="true" />
          <Confetti />
          <div className="celebrate-card">
            <Illustration name="celebrate" animated />
            <p id="raise-cel-title" className="celebrate-title">
              {celebrate.title_latin}
            </p>
            <p className="celebrate-amount">{rupees(celebrate.new_wage)}</p>
            <p className="celebrate-text" lang={HTML_LANG[celebrate.language]}>
              {celebrate.text}
            </p>
            <p className={css.celebrateYear} lang={HTML_LANG[celebrate.language]}>
              {celebrate.yearly_line}
            </p>
            {celebrate.audio_url ? (
              <PlayButton
                state={player.state}
                active={player.isCurrent(media(celebrate.audio_url))}
                progress={player.progress}
                onClick={() => void player.toggle(media(celebrate.audio_url))}
                label={player.state === "blocked" ? S.tapToPlay : S.listen}
              />
            ) : null}
            <GradientButton onClick={closeCelebration}>{S.ok}</GradientButton>
          </div>
        </div>
      ) : null}
    </Screen>
  );
}

// ------------------------------------------------------------------ hero
function Hero({ v, S, lang }: { v: RaiseCaseView; S: WorkerStrings; lang: string }) {
  const n = v.numbers;
  const max = Math.max(n.target, n.current, 1);
  const won = v.raise?.answer;
  return (
    <Card tone="glow" className={`${css.hero} ${css.rise}`}>
      <div className={css.heroTop}>
        <span className={css.avatar} aria-hidden="true">
          {(v.employer.name || "?").trim().charAt(0).toUpperCase()}
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <p className={css.heroName}>{v.employer.name_by_lang?.[raiseLangOf(lang)] || v.employer.name_display}</p>
          <p className={css.heroMeta}>
            {S.work[n.work_type] ?? n.work_label} · {S.hoursDay(String(n.hours_per_day))}
          </p>
        </div>
        <Illustration name="coins" size={56} />
      </div>
      <div className={css.compare}>
        <div className={css.compareCell}>
          <p className={css.compareLabel}>{S.yourPay}</p>
          <p className={css.compareValue}>{rupees(n.current)}</p>
        </div>
        <div className={css.compareCell}>
          <p className={css.compareLabel}>
            {S.legalFor(String(n.hours_per_day))}{" "}
            {n.is_estimate ? <StatusPill tone="estimate">{S.estimate}</StatusPill> : null}
          </p>
          <p className={css.compareValue}>≈ {rupees(n.target)}</p>
        </div>
      </div>
      <div className={css.bars} aria-hidden="true">
        <div className={css.bar}>
          <div className={`${css.barFill} ${css.barNow}`} style={{ width: `${(n.current / max) * 100}%` }} />
        </div>
        <div className={css.bar}>
          <div className={`${css.barFill} ${css.barLegal}`} style={{ width: `${(n.target / max) * 100}%` }} />
        </div>
      </div>
      {n.gap_yearly > 0 ? (
        <>
          <div className={css.yearRow}>
            <p className={css.big} aria-live="polite">
              +<CountUp value={won ? won.yearly_gain : n.gap_yearly} />
            </p>
            <p className={css.bigSub}>{S.yearHero}</p>
          </div>
          <p className={css.small}>
            {S.yearLine(rupees(n.gap_yearly))} · {S.perDay(rupees(n.per_day))}
          </p>
        </>
      ) : null}
    </Card>
  );
}

// ------------------------------------------------------------------ message + status
function MessageCard({
  r,
  S,
  employer,
  uiLang,
  player,
  note,
  onSend,
  onEdit,
}: {
  r: RaiseView;
  S: WorkerStrings;
  employer: string;
  uiLang: string;
  player: ReturnType<typeof useAudioPlayer>;
  note: string | null;
  onSend: () => void;
  onEdit: () => void;
}) {
  const audio = media(r.audio_url);
  const answered = isAnswered(r.status);
  const statusText =
    r.status === "accepted" || r.status === "stepped"
      ? S.agreed(employer)
      : r.status === "played"
        ? S.played(employer)
        : r.status === "talk"
          ? S.replied(employer)
          : r.status === "sent"
            ? S.sentWaiting(employer)
            : null;
  const replies = r.events.filter((e) => e.kind === "talk");
  const sentences = r.message.sentences;
  const disclosure = r.message.disclosure;

  return (
    <>
      {answered && r.answer ? (
        <Card tone="success" className={`${css.won} ${css.rise}`}>
          <p className={css.eyebrow}>{S.newPay}</p>
          <p className={css.wonValue}>
            {rupees(r.answer.new_wage)} <span className={css.small}>{S.fromMonth(monthLabel(r.answer.new_wage_from.slice(0, 7), uiLang))}</span>
          </p>
          {r.answer.step_up_to && r.answer.step_up_from ? (
            <p className={css.small}>{S.thenMonth(rupees(r.answer.step_up_to), monthLabel(r.answer.step_up_from.slice(0, 7), uiLang))}</p>
          ) : null}
          <p className={css.bigSub}>{S.yearWon(rupees(r.answer.yearly_gain))}</p>
          {r.agreement_url ? (
            <div className={css.links}>
              <a className="btn" href={media(r.agreement_url) ?? "#"} target="_blank" rel="noopener noreferrer">
                <FileIcon /> {S.agreement}
              </a>
            </div>
          ) : null}
        </Card>
      ) : null}

      {statusText ? (
        <div className={css.row}>
          <StatusPill tone={statusTone(r.status)}>{statusText}</StatusPill>
        </div>
      ) : null}

      {replies.length ? (
        <ul className={css.timeline}>
          {replies.map((e) => (
            <li key={e.id} className={css.timelineItem}>
              <span className={css.dot} aria-hidden="true" />
              <div className={css.reply}>
                <p className="field-label">{S.replied(employer)}</p>
                <p>{e.text_worker_lang || e.text}</p>
                {e.audio_url ? (
                  <PlayButton
                    state={player.state}
                    active={player.isCurrent(media(e.audio_url))}
                    progress={player.progress}
                    onClick={() => void player.toggle(media(e.audio_url))}
                    label={S.listen}
                  />
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      <Card className={`${css.message} ${css.rise}`}>
        <div className={css.row}>
          <p className={css.eyebrow}>{S.messageTitle(S.langName[r.message.lang])}</p>
          {!answered ? (
            <button type="button" className={css.editBtn} onClick={onEdit}>
              {S.remake}
            </button>
          ) : null}
        </div>
        {disclosure ? (
          <p className={css.disclosure} lang={HTML_LANG[r.message.lang]}>
            {disclosure}
          </p>
        ) : null}
        <p className={css.messageText} lang={HTML_LANG[r.message.lang]}>
          {sentences.join(" ")}
        </p>
        {audio ? (
          <PlayButton
            state={player.state}
            active={player.isCurrent(audio)}
            progress={player.progress}
            onClick={() => void player.toggle(audio)}
            label={player.state === "blocked" ? S.tapToPlay : S.listen}
          />
        ) : (
          <p className={css.hint}>{S.voiceFailed}</p>
        )}
        {r.message.text_worker_lang ? (
          <details className="sources">
            <summary>{S.whatItSays}</summary>
            <p className={css.messageText} style={{ fontSize: "0.95rem" }}>
              {r.message.text_worker_lang}
            </p>
          </details>
        ) : null}
      </Card>

      {!answered ? (
        <div className={css.actions}>
          <GradientButton onClick={onSend} icon={<ShareIcon />}>
            {S.send(employer)}
          </GradientButton>
          {note ? <p className={css.hint}>{note}</p> : null}
        </div>
      ) : null}
    </>
  );
}

// ------------------------------------------------------------------ edit sheet
function EditForm({
  S,
  initial,
  current,
  onSave,
}: {
  S: WorkerStrings;
  initial: { step1: number; ask: number; months: number };
  current: number;
  onSave: (c: Custom) => void;
}) {
  const [step1, setStep1] = useState(String(Math.round(initial.step1)));
  const [ask, setAsk] = useState(String(Math.round(initial.ask)));
  const [months, setMonths] = useState(String(initial.months));
  const s1 = Number(step1);
  const a = Number(ask);
  const m = Number(months);
  const valid = s1 > current && a > s1 && m >= 1 && m <= 12;
  return (
    <form
      className={css.section}
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onSave({ step1: s1, ask: a, months: Math.round(m) });
      }}
    >
      <label className={css.field}>
        <span className="field-label">{S.firstStep}</span>
        <input className={css.input} type="number" inputMode="numeric" value={step1} onChange={(e) => setStep1(e.target.value)} />
      </label>
      <label className={css.field}>
        <span className="field-label">{S.fullAmount}</span>
        <input className={css.input} type="number" inputMode="numeric" value={ask} onChange={(e) => setAsk(e.target.value)} />
      </label>
      <label className={css.field}>
        <span className="field-label">{S.months}</span>
        <input
          className={css.input}
          type="number"
          inputMode="numeric"
          min={1}
          max={12}
          value={months}
          onChange={(e) => setMonths(e.target.value)}
        />
      </label>
      <GradientButton type="submit" disabled={!valid}>
        {S.save}
      </GradientButton>
    </form>
  );
}
