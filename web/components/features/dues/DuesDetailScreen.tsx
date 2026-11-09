"use client";

// /dues/[id]: one person who owes you. Hero: what is still owed and the promise counter ("Promise made 6 times,
// broken 6 times, first promised ... (4 months ago)"). Then the chips, the promise timeline in their own words
// (each entry hash-chained), a polite reminder in their language (voice note, UPI link, share), and for chit /
// other money after 3 broken promises, the record pack (PDF) with free legal aid contacts.

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  BottomSheet,
  Card,
  CountUp,
  ErrorNote,
  GradientButton,
  Loading,
  MicButton,
  PlayButton,
  Screen,
  SkeletonCard,
  StatusPill,
} from "@/components/ui/primitives";
import { BellIcon, CheckIcon, FileIcon, LockIcon, RupeeIcon, ShareIcon } from "@/components/ui/icons";
import { useAudioPlayer, useRecorder, useT, type Recording } from "@/hooks";
import { inr, shortHash, todayIst } from "@/lib/format";
import type { UiLang } from "@/lib/i18n";
import { shareMessage, type ShareResult } from "@/lib/share";
import {
  addPaid,
  addPromise,
  duesLang,
  getDues,
  makeReminder,
  packUrl,
  promiseTone,
  setPromiseStatus,
  DuesError,
  type DuesLang,
  type DuesReminder,
  type DuesView,
} from "@/lib/features/dues";
import { DuesArt } from "./DuesArt";
import { NotAdvice, PromiseCounter, initial } from "./parts";
import { duesStrings, type DuesStrings } from "./strings";
import css from "./dues.module.css";

const HTML_LANG: Record<DuesLang, string> = { "te-IN": "te", "hi-en": "hi", en: "en" };

export function DuesDetailScreen({ id, asOf }: { id: number; asOf?: string | null }) {
  const { t, lang } = useT();
  const S = duesStrings(lang);
  const router = useRouter();
  const [v, setV] = useState<DuesView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<null | "promise" | "paid">(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setV(await getDues(id, asOf, signal));
        setError(null);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(S.error);
      } finally {
        setLoading(false);
      }
    },
    [id, asOf, S.error],
  );

  useEffect(() => {
    const ac = new AbortController();
    // load() sets state only after its fetch resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(ac.signal);
    return () => ac.abort();
  }, [load]);

  const dl = duesLang(lang);
  const a = v?.account;

  return (
    <Screen title={a ? a.party_display[dl] || a.party_name : S.title} back={`/dues${asOf ? `?as_of=${asOf}` : ""}`} t={t} className="fx">
      {loading && !v ? (
        <div role="status" aria-label={t("common.loading")} className="stack">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : null}
      {!v && !loading ? <ErrorNote message={error} onRetry={() => void load()} retryLabel={S.retry} /> : null}

      {v && a ? (
        <>
          <section className={`${css.hero} ${css.rise}`}>
            <div className={css.heroTop}>
              <span className={css.avatar} data-kind={a.kind} aria-hidden="true">
                {initial(a.party_name)}
              </span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <p className={css.heroName}>{a.party_display[dl] || a.party_name}</p>
                <p className={css.heroMeta}>{S.kinds[a.kind]}</p>
              </div>
              <DuesArt kind={a.kind} size={52} />
            </div>
            <p className={css.eyebrow}>{S.stillOwed}</p>
            <p className={css.big} aria-live="polite">
              <CountUp value={v.balance} />
            </p>
            {v.total_due > 0 ? (
              <div className={css.progress} aria-hidden="true">
                <div className={css.progressTrack}>
                  <span className={css.progressFill} style={{ width: `${Math.min(100, (v.total_paid / v.total_due) * 100)}%` }} />
                </div>
                <div className={css.progressMeta}>
                  <span>
                    {S.received} <b>{inr(v.total_paid)}</b>
                  </span>
                  <span>
                    <b>{inr(v.total_due)}</b>
                  </span>
                </div>
              </div>
            ) : null}
            <PromiseCounter counter={v.counter} promises={v.promises} S={S} lang={lang} />
          </section>

          <section className={css.section} aria-label={S.whatOwed}>
            <h2 className="section-title">{S.whatOwed}</h2>
            <ul className={css.chips}>
              {v.items.map((i, n) => (
                <li key={i.id} className={css.chip} data-kind={i.kind} style={{ animationDelay: `${n * 70}ms`, paddingRight: 12 }}>
                  <span className={css.chipLabel}>{i.kind === "paid" ? S.received : i.display[dl] || i.label}</span>
                  <span className={css.chipValue}>
                    {i.kind === "paid" ? "−" : ""}
                    {inr(i.amount)}
                  </span>
                </li>
              ))}
            </ul>
            <div className={css.actions}>
              <button type="button" className="fx-pill-btn" onClick={() => setSheet("promise")}>
                {S.theyPromised}
              </button>
              <button type="button" className="fx-pill-btn" onClick={() => setSheet("paid")} disabled={v.balance <= 0}>
                <RupeeIcon /> {S.gotPaid}
              </button>
            </div>
          </section>

          {v.can_remind ? <ReminderPanel key={`${v.balance}-${v.promises.length}`} v={v} S={S} asOf={asOf} /> : null}

          {v.pack.applies ? <PackCard v={v} S={S} asOf={asOf} /> : null}

          {v.promises.length ? (
            <section className={css.section} aria-label={S.timeline}>
              <h2 className="section-title">{S.timeline}</h2>
              <ol className={css.timeline}>
                {[...v.promises].reverse().map((p, n) => (
                  <li key={p.id} className={css.tItem} data-status={p.status} style={{ animationDelay: `${n * 60}ms` }}>
                    <div className={css.tHead}>
                      <p className={css.tWhen}>{S.saidOn(p.said_display[dl])}</p>
                      <StatusPill tone={promiseTone(p.status)}>{S.status[p.status]}</StatusPill>
                    </div>
                    <p className={css.quote} lang={HTML_LANG[p.lang]}>
                      “{p.quote}”
                    </p>
                    <p className={css.tDue}>
                      {S.dueBy(p.due_display[dl])}
                      {p.amount_display ? ` · ${p.amount_display}` : ""}
                    </p>
                    <p className={css.hash}>#{shortHash(p.hash)}</p>
                    {p.status === "pending" ? (
                      <div className={css.tActions}>
                        <StatusButtons id={p.id} S={S} asOf={asOf} onDone={setV} />
                      </div>
                    ) : null}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          <p className={css.chain} data-ok={v.chain.valid}>
            <LockIcon /> {v.chain.valid ? S.chainOk(v.chain.count) : S.chainBroken}
          </p>

          {a.demo ? (
            <label className={css.travel}>
              <span>{S.timeTravel}</span>
              <input
                className="input"
                type="date"
                value={asOf ?? v.as_of}
                onChange={(e) => router.replace(`/dues/${id}${e.target.value ? `?as_of=${e.target.value}` : ""}`)}
              />
              {asOf ? (
                <button type="button" className="btn btn-small" onClick={() => router.replace(`/dues/${id}`)}>
                  {S.today}
                </button>
              ) : null}
            </label>
          ) : null}
          <NotAdvice S={S} />

          <PromiseSheet open={sheet === "promise"} onClose={() => setSheet(null)} v={v} S={S} lang={lang} asOf={asOf} onDone={setV} />
          <PaidSheet open={sheet === "paid"} onClose={() => setSheet(null)} v={v} S={S} asOf={asOf} onDone={setV} />
        </>
      ) : null}
    </Screen>
  );
}

function StatusButtons({ id, S, asOf, onDone }: { id: number; S: DuesStrings; asOf?: string | null; onDone: (v: DuesView) => void }) {
  const [busy, setBusy] = useState(false);
  async function mark(status: "kept" | "broken") {
    setBusy(true);
    try {
      onDone(await setPromiseStatus(id, status, asOf));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button type="button" className="fx-pill-btn" disabled={busy} onClick={() => void mark("kept")}>
        <CheckIcon /> {S.markKept}
      </button>
      <button type="button" className="fx-pill-btn" disabled={busy} onClick={() => void mark("broken")}>
        {S.markBroken}
      </button>
    </>
  );
}

// ------------------------------------------------------------------ reminder
function ReminderPanel({ v, S, asOf }: { v: DuesView; S: DuesStrings; asOf?: string | null }) {
  const [rem, setRem] = useState<DuesReminder | null>(null);
  const [voice, setVoice] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [shared, setShared] = useState<ShareResult | null>(null);
  const player = useAudioPlayer();
  const a = v.account;

  async function make() {
    setBusy(true);
    setErr(null);
    try {
      const r = await makeReminder(a.id, { voice, asOf });
      setRem(r);
      if (r.audio_url) void player.play(r.audio_url);
    } catch {
      setErr(S.error);
    } finally {
      setBusy(false);
    }
  }

  async function share() {
    if (!rem) return;
    let file: File | null = null;
    if (rem.audio_url) {
      try {
        const res = await fetch(rem.audio_url);
        file = new File([await res.blob()], "baaki-reminder.ogg", { type: "audio/ogg" });
      } catch {
        file = null;
      }
    }
    setShared(await shareMessage({ text: rem.share_text, file }));
  }

  return (
    <section className={`${css.panel} ${css.rise}`} aria-live="polite">
      <div className="stack">
        <div className={css.panelHead}>
          <span className={css.panelIcon} aria-hidden="true">
            <BellIcon />
          </span>
          <div>
            <p className={css.tileTitle}>{S.remindTitle}</p>
            <p className={css.tileHint}>{S.remindHint(S.langs[a.party_lang])}</p>
          </div>
        </div>
        {!rem ? (
          <>
            <label className="toggle">
              <input type="checkbox" checked={voice} onChange={(e) => setVoice(e.target.checked)} />
              <span className="toggle-track" aria-hidden="true" />
              <span className="toggle-label">{S.withVoice}</span>
            </label>
            <GradientButton onClick={() => void make()} disabled={busy} icon={<BellIcon />}>
              {S.makeReminder}
            </GradientButton>
            {busy ? <Loading label={S.reading} /> : null}
          </>
        ) : (
          <>
            <div className={`${css.bubble} ${css.pop}`}>
              <p className={css.message} lang={HTML_LANG[rem.language]}>
                {rem.text}
              </p>
              {rem.checks.amounts_ok && rem.checks.no_accusation ? (
                <StatusPill tone="success" dot={false}>
                  <CheckIcon /> {S.checksOk}
                </StatusPill>
              ) : null}
            </div>
            {rem.audio_url ? (
              <PlayButton
                state={player.state}
                active={player.src === rem.audio_url}
                progress={player.progress}
                onClick={() => void player.toggle(rem.audio_url!)}
                label={S.voiceNote}
              />
            ) : null}
            {rem.audio_error ? <p className="hint">{S.voiceFailed}</p> : null}
            {rem.owner_language !== rem.language ? (
              <details className={css.block}>
                <summary className={css.blockLabel}>{S.inYourLang}</summary>
                <p className={css.message} lang={HTML_LANG[rem.owner_language]}>
                  {rem.text_owner_lang}
                </p>
              </details>
            ) : null}
            {rem.upi_url ? (
              <p className={css.hash} title={S.upiLink}>
                {S.upiLink}: {rem.upi_url}
              </p>
            ) : null}
            <div className={css.actions}>
              <button type="button" className="fx-pill-btn" data-ink onClick={() => void share()}>
                <ShareIcon /> {S.share}
              </button>
              <a className="fx-pill-btn" href={rem.whatsapp_url} target="_blank" rel="noreferrer">
                {S.whatsapp}
              </a>
            </div>
            {shared === "copied" ? <p className="hint">{S.copied}</p> : null}
            <p className="hint">{S.youSend}</p>
          </>
        )}
        <ErrorNote message={err} />
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ record pack
function PackCard({ v, S, asOf }: { v: DuesView; S: DuesStrings; asOf?: string | null }) {
  const left = Math.max(v.pack.min_broken - v.counter.broken, 0);
  return (
    <Card tone={v.pack.eligible ? "warn" : "soft"} className={css.rise}>
      <div className="stack">
        <div className={css.packHead}>
          <span className={css.packIcon} aria-hidden="true">
            <FileIcon />
          </span>
          <div>
            <p className={css.tileTitle}>{v.pack.eligible ? S.packTitle : S.packLocked(v.pack.min_broken, left)}</p>
            {v.pack.eligible ? <p className={css.tileHint}>{S.packBody(v.counter.broken)}</p> : null}
          </div>
        </div>
        {v.pack.eligible ? (
          <a className="btn btn-big" href={packUrl(v.account.id, asOf)} target="_blank" rel="noreferrer">
            <FileIcon /> {S.openPack}
          </a>
        ) : null}
        <p className="hint">{S.helpLine}</p>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ sheets
function PromiseSheet({
  open,
  onClose,
  v,
  S,
  lang,
  asOf,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  v: DuesView;
  S: DuesStrings;
  lang: UiLang;
  asOf?: string | null;
  onDone: (v: DuesView) => void;
}) {
  const [mode, setMode] = useState<"speak" | "type">("type");
  const [text, setText] = useState("");
  const [rec, setRec] = useState<Recording | null>(null);
  const [saidOn, setSaidOn] = useState(() => asOf ?? todayIst());
  const [due, setDue] = useState("");
  const [needDate, setNeedDate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const recorder = useRecorder({ onRecorded: useCallback((r: Recording) => setRec(r), []), maxMs: 30_000 });
  const ready = (mode === "type" && text.trim().length > 0) || (mode === "speak" && !!rec);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const out = await addPromise(v.account.id, {
        text: mode === "type" ? text.trim() : undefined,
        audio: mode === "speak" ? rec?.blob ?? null : null,
        filename: rec?.filename,
        saidOn,
        dueDate: due || null,
        lang: v.account.party_lang === "te-IN" ? "te" : v.account.party_lang === "hi-en" ? "hinglish" : "en",
        asOf: asOf ?? null,
      });
      onDone(out);
      setText("");
      setRec(null);
      setDue("");
      setNeedDate(false);
      onClose();
    } catch (e) {
      if (e instanceof DuesError && e.code === "no_date") {
        setNeedDate(true);
        setErr(S.noDate);
      } else setErr(S.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet open={open} onClose={busy ? () => undefined : onClose} title={S.promiseSheet} closeLabel={S.cancel}>
      <div className={css.sheetBody}>
        <p className="hint">{S.promiseHint}</p>
        <div className="segmented" role="group">
          <button type="button" aria-pressed={mode === "type"} onClick={() => setMode("type")}>
            {S.tabType}
          </button>
          <button type="button" aria-pressed={mode === "speak"} onClick={() => setMode("speak")}>
            {S.tabSpeak}
          </button>
        </div>
        {mode === "type" ? (
          <textarea
            className="input"
            rows={2}
            value={text}
            maxLength={2000}
            placeholder={S.promisePlaceholder}
            lang={HTML_LANG[duesLang(lang)]}
            onChange={(e) => setText(e.target.value)}
          />
        ) : (
          <MicButton
            state={recorder.state}
            level={recorder.level}
            elapsedMs={recorder.elapsedMs}
            size="small"
            disabled={busy}
            handlers={{ onClick: recorder.toggle }}
            label={recorder.state === "recording" ? S.recordStop : S.recordStart}
          />
        )}
        <div className={css.twoCol}>
          <label className="field">
            <span className="field-label">{S.saidOnLabel}</span>
            <input className="input" type="date" value={saidOn} max={asOf ?? todayIst()} onChange={(e) => setSaidOn(e.target.value)} />
          </label>
          {needDate ? (
            <label className="field">
              <span className="field-label">{S.dueLabel}</span>
              <input className="input" type="date" value={due} min={saidOn} onChange={(e) => setDue(e.target.value)} />
            </label>
          ) : null}
        </div>
        {busy ? <Loading label={S.reading} /> : null}
        <ErrorNote message={err} />
        <GradientButton onClick={() => void submit()} disabled={!ready || busy || (needDate && !due)}>
          {S.addPromise}
        </GradientButton>
      </div>
    </BottomSheet>
  );
}

function PaidSheet({
  open,
  onClose,
  v,
  S,
  asOf,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  v: DuesView;
  S: DuesStrings;
  asOf?: string | null;
  onDone: (v: DuesView) => void;
}) {
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const n = Number(amount);
  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      onDone(await addPaid(v.account.id, n, asOf));
      setAmount("");
      onClose();
    } catch {
      setErr(S.error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <BottomSheet open={open} onClose={busy ? () => undefined : onClose} title={S.paidSheet} closeLabel={S.cancel}>
      <div className={css.sheetBody}>
        <label className="field">
          <span className="field-label">{S.paidAmount}</span>
          <input className="input" type="number" inputMode="numeric" min={1} value={amount} placeholder={String(v.balance)} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <button type="button" className="btn btn-small" onClick={() => setAmount(String(v.balance))}>
          {inr(v.balance)}
        </button>
        <ErrorNote message={err} />
        <GradientButton onClick={() => void submit()} disabled={!(n > 0) || busy}>
          {S.gotPaid}
        </GradientButton>
      </div>
    </BottomSheet>
  );
}
