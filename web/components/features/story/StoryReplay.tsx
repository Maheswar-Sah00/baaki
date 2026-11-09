"use client";

// V12 Case Replay: one case from first word to payment, using only the stored events and their stored times.
// Functional, not polished (another session owns the design). Events drop in one after another; the meter
// falls with each payment (balance_after comes from the server, which uses the case screen's Case.balance).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useT } from "@/hooks";
import { getStory, rupees, storyLang, timeLabel, type Story, type StoryEvent } from "@/lib/features/story";
import { storyStrings } from "./strings";
import css from "./story.module.css";

const TOTAL_MS = 15000; // the whole case in about 15 seconds
const STEP_MIN = 350;
const STEP_MAX = 1400;

function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function StoryReplay({ caseId }: { caseId: number }) {
  const { lang: ui } = useT();
  const lang = storyLang(ui);
  const S = storyStrings(lang);
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState(0);
  const [run, setRun] = useState(0); // bumps on every Play
  const [playingUrl, setPlayingUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    getStory(caseId, ac.signal)
      .then((s) => {
        setStory(s);
        setError(null);
        setRun(1);
      })
      .catch((e: unknown) => {
        if (ac.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
      });
    return () => ac.abort();
  }, [caseId]);

  const n = story?.events.length ?? 0;

  // reveal events one by one (all at once with reduced motion)
  useEffect(() => {
    if (!story || run === 0) return;
    if (reducedMotion()) {
      setShown(n);
      return;
    }
    setShown(0);
    const step = Math.min(STEP_MAX, Math.max(STEP_MIN, Math.floor(TOTAL_MS / Math.max(1, n + 1))));
    let i = 0;
    const t = window.setInterval(() => {
      i += 1;
      setShown(i);
      if (i >= n) window.clearInterval(t);
    }, step);
    return () => window.clearInterval(t);
  }, [story, run, n]);

  useEffect(() => () => audioRef.current?.pause(), []);

  const toggleAudio = useCallback((url: string) => {
    const cur = audioRef.current;
    if (cur && playingUrl === url) {
      cur.pause();
      setPlayingUrl(null);
      return;
    }
    cur?.pause();
    const a = new Audio(url);
    audioRef.current = a;
    a.onended = () => setPlayingUrl(null);
    a.onerror = () => setPlayingUrl(null);
    setPlayingUrl(url);
    void a.play().catch(() => setPlayingUrl(null));
  }, [playingUrl]);

  // the meter: the balance after the last payment shown so far, else the case total
  const meter = useMemo(() => {
    if (!story) return 0;
    let bal = story.total_due;
    for (const e of story.events.slice(0, shown)) if (typeof e.balance_after === "number") bal = e.balance_after;
    return bal;
  }, [story, shown]);

  if (error) return <main className={css.page}><p className={css.error}>{error}</p></main>;
  if (!story) return <main className={css.page}><p className={css.muted}>{S.loading}</p></main>;

  const done = shown >= n;
  return (
    <main className={css.page}>
      <header className={css.head}>
        <p className={css.kicker}>{S.kicker}</p>
        <h1 className={css.title}>{S.title(story.case.worker.name, story.case.employer.name)}</h1>
        <div className={css.meter} aria-live="polite">
          <span className={css.meterLabel}>{S.owed}</span>
          <span className={css.meterValue}>{rupees(meter)}</span>
          <span className={css.meterOf}>{S.of(rupees(story.total_due))}</span>
        </div>
        <button type="button" className={css.play} onClick={() => setRun((r) => r + 1)}>
          {run > 1 || done ? S.replay : S.play}
        </button>
      </header>

      <ol className={css.list}>
        {story.events.slice(0, shown).map((e) => (
          <EventRow key={`${run}-${e.seq}`} e={e} lang={lang} S={S} playingUrl={playingUrl} onAudio={toggleAudio} />
        ))}
      </ol>

      {done && (
        <section className={css.end}>
          {story.paid_in_full ? (
            <p className={css.endWin}>{S.paidFull}</p>
          ) : (
            <p className={css.endOwed}>{S.stillOwed(rupees(story.balance))}</p>
          )}
          {story.untimed.length > 0 && (
            <ul className={css.untimed}>
              {story.untimed.map((u) => (
                <li key={`${u.source_table}-${u.source_id}-${u.kind}`}>{u.title[lang]}</li>
              ))}
            </ul>
          )}
          <p className={css.muted}>{S.footnote}</p>
        </section>
      )}
    </main>
  );
}

function EventRow({
  e,
  lang,
  S,
  playingUrl,
  onAudio,
}: {
  e: StoryEvent;
  lang: "en" | "te" | "hi";
  S: ReturnType<typeof storyStrings>;
  playingUrl: string | null;
  onAudio: (url: string) => void;
}) {
  const t = timeLabel(e.at);
  const isPay = e.kind === "paid";
  const isWin = e.kind === "paid_alert";
  return (
    <li className={`${css.item} ${isPay ? css.pay : ""} ${isWin ? css.win : ""}`}>
      <time className={css.when} dateTime={e.at} title={`${e.at} (${e.at_field})`}>
        <span>{t.date}</span>
        <span className={css.clock}>{t.time}</span>
      </time>
      <div className={css.body}>
        <p className={css.what}>
          <span className={css.tick} aria-hidden="true">✓</span> {e.title[lang]}
          {isPay && typeof e.amount === "number" && <strong className={css.amount}> {rupees(e.amount)}</strong>}
        </p>
        {isPay && typeof e.balance_after === "number" && (
          <p className={css.balance}>{S.left(rupees(e.balance_after))}</p>
        )}
        {e.text && !isPay && <p className={css.quote}>{e.text_worker_lang ?? e.text}</p>}
        <div className={css.chips}>
          {e.audio_url && (
            <button type="button" className={css.chip} onClick={() => onAudio(e.audio_url!)}>
              {playingUrl === e.audio_url ? S.stop : S.listen}
            </button>
          )}
          {e.original_audio_url && (
            <button type="button" className={css.chip} onClick={() => onAudio(e.original_audio_url!)}>
              {playingUrl === e.original_audio_url ? S.stop : S.listenOriginal}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}
