"use client";

// V12 Case Replay (/story/[id]): one case from first word to payment, using only the stored events and their stored
// times. A quiet, cinematic replay: a stage card whose illustration follows the chapter (she spoke -> letter and voice
// note -> the employer answered -> paid), the "still owed" figure easing down with each payment (balance_after comes
// from the server), and a timeline that lights up step by step. Reduced motion shows everything at once.

import { useEffect, useMemo, useRef, useState } from "react";
import { useAudioPlayer, useT } from "@/hooks";
import { easeOutCubic, prefersReducedMotion } from "@/lib/easing";
import { getStory, rupees, storyLang, timeLabel, type Story, type StoryEvent } from "@/lib/features/story";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { ErrorNote, Illustration, PlayButton, Screen, SkeletonCard } from "@/components/ui/primitives";
import {
  ArrowRightIcon,
  CheckIcon,
  ClockIcon,
  CrossIcon,
  DiaryIcon,
  DoorIcon,
  InboxIcon,
  MicIcon,
  PauseIcon,
  PlayIcon,
  RupeeIcon,
  ShieldIcon,
  SparkIcon,
  WaveIcon,
} from "@/components/ui/icons";
import { storyStrings, type Chapter, type StoryStrings } from "./strings";
import css from "./story.module.css";

const TOTAL_MS = 15000; // the whole case in about 15 seconds
const STEP_MIN = 350;
const STEP_MAX = 1400;

const CHAPTER_OF: Record<string, Chapter> = {
  note_made: "letter",
  listen_twice: "letter",
  listen_twice_warn: "letter",
  sent: "letter",
  employer_replied: "deal",
  reply_translated: "deal",
  reply_saved: "deal",
  plan_chosen: "deal",
  promised: "deal",
  promise_kept: "deal",
  promise_broken: "deal",
  exit_kit: "deal",
  paid: "paid",
  paid_alert: "paid",
};
const WASH: Record<Chapter, string> = { speak: "lilac", letter: "sky", deal: "butter", paid: "sage" };

function iconFor(kind: string) {
  switch (kind) {
    case "spoke":
      return <MicIcon />;
    case "readback_confirmed":
    case "listen_twice":
    case "promise_kept":
      return <CheckIcon />;
    case "evidence_saved":
      return <ShieldIcon />;
    case "note_made":
      return <WaveIcon />;
    case "sent":
      return <ArrowRightIcon />;
    case "employer_replied":
    case "reply_translated":
    case "reply_saved":
      return <InboxIcon />;
    case "plan_chosen":
    case "promised":
    case "listen_twice_warn":
      return <ClockIcon />;
    case "promise_broken":
      return <CrossIcon />;
    case "paid":
      return <RupeeIcon />;
    case "paid_alert":
      return <SparkIcon />;
    case "exit_kit":
      return <DoorIcon />;
    default:
      return <DiaryIcon />;
  }
}

/** Eases a number towards `target` (set only from rAF callbacks; reduced motion lands on the next frame). */
function useEased(target: number, ms = 700): number {
  const [value, setValue] = useState(target);
  const current = useRef(target);
  useEffect(() => {
    const from = current.current;
    const dur = prefersReducedMotion() ? 0 : ms;
    const t0 = performance.now();
    let raf = requestAnimationFrame(function tick(now) {
      const p = dur ? Math.min(1, (now - t0) / dur) : 1;
      current.current = from + (target - from) * easeOutCubic(p);
      setValue(current.current);
      if (p < 1) raf = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return value;
}

function StageArt({ chapter }: { chapter: Chapter }) {
  if (chapter === "letter") {
    return (
      <span className={css.art} data-bleed="sides">
        <AssetSlot name="can-do-letter-voice" alt="" ratio="1600/753" tone="sky" fit="contain" rounded="0" priority />
      </span>
    );
  }
  const name = chapter === "speak" ? "speak" : chapter === "deal" ? "handshake" : "celebrate";
  return (
    <span className={css.art} data-bleed={chapter === "deal" ? "none" : "bottom"} data-chapter={chapter}>
      <Illustration name={name} />
    </span>
  );
}

export function StoryReplay({ caseId }: { caseId: number }) {
  const { t, lang: ui } = useT();
  const lang = storyLang(ui);
  const S = storyStrings(lang);
  const player = useAudioPlayer();
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState(0);
  const [playing, setPlaying] = useState(false);
  const itemRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    const ac = new AbortController();
    getStory(caseId, ac.signal)
      .then((s) => {
        setStory(s);
        setError(null);
        if (prefersReducedMotion()) {
          setShown(s.events.length);
          setPlaying(false);
        } else {
          setShown(0);
          setPlaying(true);
        }
      })
      .catch((e: unknown) => {
        if (ac.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
      });
    return () => ac.abort();
  }, [caseId]);

  const n = story?.events.length ?? 0;
  const done = shown >= n;
  const step = Math.min(STEP_MAX, Math.max(STEP_MIN, Math.floor(TOTAL_MS / Math.max(1, n + 1))));

  // Reveal the next event on every tick while playing (no interval once everything is shown).
  useEffect(() => {
    if (!playing || done) return;
    const id = window.setInterval(() => setShown((i) => Math.min(n, i + 1)), step);
    return () => window.clearInterval(id);
  }, [playing, done, n, step]);

  // Keep the step that just lit up in view (only when it would otherwise be below the fold).
  useEffect(() => {
    if (!playing || shown === 0 || prefersReducedMotion()) return;
    const el = itemRefs.current[shown - 1];
    if (el && el.getBoundingClientRect().bottom > window.innerHeight - 16) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [shown, playing]);

  // The meter: the balance after the last payment shown so far, else the case total.
  const target = useMemo(() => {
    if (!story) return 0;
    let bal = story.total_due;
    for (const e of story.events.slice(0, shown)) if (typeof e.balance_after === "number") bal = e.balance_after;
    return bal;
  }, [story, shown]);
  const meter = useEased(target);

  const back = `/case/${caseId}`;
  if (error) {
    return (
      <Screen title={S.kicker} back={back} t={t} className={`fx ${css.screen}`}>
        <ErrorNote message={error} />
      </Screen>
    );
  }
  if (!story) {
    return (
      <Screen title={S.kicker} back={back} t={t} className={`fx ${css.screen}`}>
        <div className="stack" role="status" aria-label={S.loading}>
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </Screen>
    );
  }

  const last = shown > 0 ? story.events[shown - 1] : null;
  const chapter: Chapter = done && story.paid_in_full ? "paid" : last ? CHAPTER_OF[last.kind] ?? "speak" : "speak";
  const paidShare = story.total_due > 0 ? Math.min(1, Math.max(0, 1 - meter / story.total_due)) : 0;
  const control = () => {
    if (done) {
      player.stop();
      setShown(0);
      setPlaying(true);
    } else setPlaying((p) => !p);
  };
  const htmlLang = lang === "te" ? "te" : lang === "hi" ? "hi" : "en";

  return (
    <Screen title={S.kicker} back={back} t={t} className={`fx ${css.screen}`}>
      <header className={css.head} lang={htmlLang}>
        <p className="fx-eyebrow">{S.kicker}</p>
        <h1 className={`fx-h ${css.title}`}>
          {story.case.worker.name} <em>{S.and}</em> {story.case.employer.name}
        </h1>
      </header>

      <section className={css.stage} aria-label={S.owed} lang={htmlLang}>
        <div className={css.scene} data-wash={WASH[chapter]}>
          <StageArt key={chapter} chapter={chapter} />
          <span key={`c-${chapter}`} className={css.sceneTag}>
            {S.chapter[chapter]}
          </span>
        </div>
        <div className={css.meterRow}>
          <div className={css.meter} aria-live="polite" aria-atomic="true">
            <span className={css.meterLabel}>{S.owed}</span>
            <span className={css.meterValue}>{rupees(meter)}</span>
            <span className={css.meterOf}>{S.of(rupees(story.total_due))}</span>
          </div>
          <button type="button" className={css.play} onClick={control} aria-pressed={playing && !done}>
            <span className={css.playIcon} aria-hidden="true">
              {playing && !done ? <PauseIcon /> : <PlayIcon />}
            </span>
            {done ? S.replay : playing ? S.pause : shown > 0 ? S.resume : S.play}
          </button>
        </div>
        <div className={css.progress} aria-hidden="true">
          <span style={{ transform: `scaleX(${n ? shown / n : 0})` }} />
        </div>
        <div className={css.progressMeta}>
          <span>{S.step(Math.min(shown, n), n)}</span>
          {paidShare > 0 ? <span>{Math.round(paidShare * 100)}%</span> : null}
        </div>
      </section>

      <ol className={css.list} lang={htmlLang}>
        {story.events.map((e, i) => (
          <EventRow
            key={e.seq}
            e={e}
            lang={lang}
            S={S}
            state={i < shown ? (i === shown - 1 && !done ? "current" : "done") : "todo"}
            player={player}
            refCb={(el) => {
              itemRefs.current[i] = el;
            }}
          />
        ))}
      </ol>

      {done ? (
        <section className={css.end} lang={htmlLang}>
          {story.paid_in_full ? (
            <p className={css.endWin} data-wash="sage">
              <CheckIcon /> {S.paidFull}
            </p>
          ) : (
            <p className={css.endOwed}>{S.stillOwed(rupees(story.balance))}</p>
          )}
          {story.untimed.length > 0 ? (
            <div className={css.untimed}>
              <p className="fx-eyebrow">{S.untimed}</p>
              <ul>
                {story.untimed.map((u) => (
                  <li key={`${u.source_table}-${u.source_id}-${u.kind}`}>{u.title[lang]}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="fx-muted">{S.footnote}</p>
        </section>
      ) : null}
    </Screen>
  );
}

function EventRow({
  e,
  lang,
  S,
  state,
  player,
  refCb,
}: {
  e: StoryEvent;
  lang: "en" | "te" | "hi";
  S: StoryStrings;
  state: "done" | "current" | "todo";
  player: ReturnType<typeof useAudioPlayer>;
  refCb: (el: HTMLLIElement | null) => void;
}) {
  const tl = timeLabel(e.at);
  const isPay = e.kind === "paid";
  const isWin = e.kind === "paid_alert";
  const quote = e.text && !isPay ? e.text_worker_lang ?? e.text : null;
  return (
    <li ref={refCb} className={css.item} data-state={state} data-kind={isPay ? "pay" : isWin ? "win" : undefined}>
      <span className={css.node} aria-hidden="true">
        {iconFor(e.kind)}
      </span>
      <div className={css.body}>
        <time className={css.when} dateTime={e.at} title={`${e.at} (${e.at_field})`}>
          {tl.date}
          {tl.time ? ` · ${tl.time}` : ""}
        </time>
        <p className={css.what}>{e.title[lang]}</p>
        {isPay && typeof e.amount === "number" ? (
          <p className={css.amount}>
            {rupees(e.amount)}
            {typeof e.balance_after === "number" ? <span>{S.left(rupees(e.balance_after))}</span> : null}
          </p>
        ) : null}
        {quote ? <p className={css.quote}>{quote}</p> : null}
        {state !== "todo" && (e.audio_url || e.original_audio_url) ? (
          <div className={css.chips}>
            {e.audio_url ? (
              <PlayButton
                state={player.state}
                active={player.isCurrent(e.audio_url)}
                progress={player.progress}
                onClick={() => void player.toggle(e.audio_url)}
                label={player.isCurrent(e.audio_url) && player.playing ? S.stop : S.listen}
              />
            ) : null}
            {e.original_audio_url ? (
              <PlayButton
                state={player.state}
                active={player.isCurrent(e.original_audio_url)}
                progress={player.progress}
                onClick={() => void player.toggle(e.original_audio_url)}
                label={player.isCurrent(e.original_audio_url) && player.playing ? S.stop : S.listenOriginal}
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}
