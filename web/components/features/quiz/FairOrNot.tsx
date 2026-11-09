"use client";

// Fair or Not? (V08): five myth cards for employers. One card at a time: tap Fair / Not fair -> the rule with its
// section and source (and the cached Hinglish narration) -> next -> a clean score card to share.
// Phone: one column with a progress bar. Desktop: the five cards as a numbered list on the left (active = ink,
// like Vyra's "What your AI can do"), the card on the right. Card text, labels and the disclaimer come from the API.

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Logo, LogoMark } from "@/components/ui/Logo";
import { Illustration, PlayButton, Skeleton, ThemeToggle } from "@/components/ui/primitives";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { ArrowRightIcon, CheckIcon, CrossIcon, ShareIcon } from "@/components/ui/icons";
import { useAudioPlayer } from "@/hooks";
import { prefersReducedMotion } from "@/lib/easing";
import {
  answerCard,
  getDeck,
  scoreQuiz,
  shareScore,
  type QuizChoice,
  type QuizDeck,
  type QuizLang,
  type QuizReveal,
  type QuizScore,
} from "@/lib/features/quiz";
import { LANG_OPTIONS, makeT } from "./strings";
import css from "./quiz.module.css";

const LANG_KEY = "baaki.quiz.lang";
const WASHES = ["sky", "peach", "lilac", "butter", "sage"] as const;

// The remembered language is a per-viewer convenience. Reading it through useSyncExternalStore keeps the server
// render and hydration in agreement; blocked storage just reads as "nothing saved".
function readSavedLang(): QuizLang | null {
  try {
    const v = window.localStorage.getItem(LANG_KEY);
    return LANG_OPTIONS.some((o) => o.id === v) ? (v as QuizLang) : null;
  } catch {
    return null;
  }
}
function subscribeStorage(onChange: () => void) {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

const pad = (n: number) => String(n).padStart(2, "0");

/** "Fair or Not?" -> ["Fair or", "Not?"]: the last word takes the serif accent. */
function splitTitle(title: string): [string, string] {
  const s = title.trim();
  const i = s.lastIndexOf(" ");
  return i > 0 ? [s.slice(0, i), s.slice(i + 1)] : ["", s];
}

type Phase = "loading" | "ask" | "reveal" | "score" | "error";

export function FairOrNot() {
  const saved = useSyncExternalStore(subscribeStorage, readSavedLang, () => null);
  const [picked, setPicked] = useState<QuizLang | null>(null);
  const lang: QuizLang = picked ?? saved ?? "en";
  const [deck, setDeck] = useState<QuizDeck | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, QuizChoice>>({});
  const [marks, setMarks] = useState<Record<string, boolean | null>>({});
  const [reveal, setReveal] = useState<QuizReveal | null>(null);
  const [result, setResult] = useState<QuizScore | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [choosing, setChoosing] = useState<QuizChoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [shareNote, setShareNote] = useState<string | null>(null);
  const player = useAudioPlayer();
  const t = makeT(lang);
  const firstLoad = useRef(true);
  const stageRef = useRef<HTMLElement>(null);

  // Load the deck for the language; progress is kept across a language switch.
  useEffect(() => {
    const ac = new AbortController();
    getDeck(lang, ac.signal)
      .then((d) => {
        setDeck(d);
        if (firstLoad.current) {
          firstLoad.current = false;
          setPhase("ask");
        }
      })
      .catch((err: unknown) => {
        if (!(err instanceof DOMException && err.name === "AbortError")) setPhase("error");
      });
    return () => ac.abort();
  }, [lang]);

  const pickLang = (l: QuizLang) => {
    if (l === lang) return;
    setPicked(l);
    try {
      window.localStorage.setItem(LANG_KEY, l);
    } catch {
      /* storage blocked */
    }
    // Re-translate a shown answer or score in the new language.
    if (phase === "reveal" && reveal?.choice) answerCard(reveal.id, reveal.choice, l).then(setReveal).catch(() => undefined);
    else if (phase === "score" && result) scoreQuiz(answers, l).then(setResult).catch(() => undefined);
  };

  /** Bring the card back into view after it changes (phones, when the reveal was long). */
  const toStage = () => {
    requestAnimationFrame(() => {
      const el = stageRef.current;
      if (el && el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: "start", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    });
  };

  const card = deck?.cards[index] ?? null;
  const isLast = deck ? index >= deck.total - 1 : false;

  const choose = async (choice: QuizChoice) => {
    if (!card || busy) return;
    setBusy(true);
    setChoosing(choice);
    try {
      const r = await answerCard(card.id, choice, lang);
      setAnswers((a) => ({ ...a, [card.id]: choice }));
      setMarks((m) => ({ ...m, [card.id]: r.correct }));
      setReveal(r);
      setPhase("reveal");
    } catch {
      setPhase("error");
    } finally {
      setBusy(false);
      setChoosing(null);
    }
  };

  const next = async () => {
    if (!deck) return;
    player.stop();
    if (!isLast) {
      setIndex((i) => i + 1);
      setReveal(null);
      setPhase("ask");
      toStage();
      return;
    }
    setBusy(true);
    try {
      setResult(await scoreQuiz(answers, lang));
      setPhase("score");
      toStage();
    } catch {
      setPhase("error");
    } finally {
      setBusy(false);
    }
  };

  const restart = () => {
    player.stop();
    setIndex(0);
    setAnswers({});
    setMarks({});
    setReveal(null);
    setResult(null);
    setShareNote(null);
    setPhase(deck ? "ask" : "loading");
    toStage();
  };

  const share = async () => {
    if (!result) return;
    const url = `${window.location.origin}/quiz`;
    const r = await shareScore(result.share_text, url);
    setShareNote(r === "shared" ? t("shared") : r === "copied" ? t("copied") : r === "failed" ? t("share_failed") : null);
  };

  const [lead, accent] = splitTitle(deck?.title ?? "Fair or Not?");
  const htmlLang = LANG_OPTIONS.find((o) => o.id === lang)?.html ?? "en";
  const answered = Object.keys(answers).length;

  return (
    <main className={css.page} lang={htmlLang}>
      <div className={css.sky} aria-hidden="true" />
      <header className={css.nav}>
        <Link href="/" className={css.brand} aria-label="Baaki home">
          <Logo size={30} telugu={false} />
        </Link>
        <div className={css.navRight}>
          <span className={css.navTag} lang="en">
            {t("tag")}
          </span>
          <ThemeToggle />
        </div>
      </header>

      <div className={css.layout}>
        <section className={css.intro}>
          <div className={css.introTop}>
            <div className={css.introText}>
              <p className={css.kicker}>{t("kicker")}</p>
              <h1 className={css.title} lang="en">
                {lead} <em>{accent}</em>
              </h1>
            </div>
            <AssetSlot name="check-payday-envelope" alt="" ratio="1300/991" tone="butter" fit="contain" priority className={css.introArt} rounded="24px" />
          </div>
          {deck ? <p className={css.sub}>{deck.intro}</p> : <Skeleton lines={2} height={16} className={css.subSkel} />}
          <div className={css.langs} role="group" aria-label={t("language")}>
            {LANG_OPTIONS.map((o) => (
              <button key={o.id} type="button" lang={o.html} aria-pressed={o.id === lang} onClick={() => pickLang(o.id)}>
                {o.label}
              </button>
            ))}
          </div>
          {deck ? (
            <ol className={css.index} aria-label={t("progress")}>
              {deck.cards.map((c, i) => {
                const mark = marks[c.id];
                const state = phase === "score" ? "done" : i === index ? "active" : answers[c.id] ? "done" : "todo";
                return (
                  <li key={c.id} data-state={state} aria-current={state === "active" ? "step" : undefined}>
                    <span className={css.indexNo}>{pad(c.n)}</span>
                    <span className={css.indexText}>{c.myth}</span>
                    {mark === true || mark === false ? (
                      <span className={css.mark} data-ok={mark} aria-hidden="true">
                        {mark ? <CheckIcon /> : <CrossIcon />}
                      </span>
                    ) : null}
                  </li>
                );
              })}
            </ol>
          ) : null}
        </section>

        <section className={css.stage} ref={stageRef} aria-live="polite">
          {deck && phase !== "score" && phase !== "error" ? (
            <div
              className={css.progress}
              role="progressbar"
              aria-label={t("progress")}
              aria-valuemin={0}
              aria-valuemax={deck.total}
              aria-valuenow={answered}
            >
              {deck.cards.map((c, i) => (
                <span key={c.id} data-state={answers[c.id] ? "done" : i === index ? "active" : "todo"} />
              ))}
            </div>
          ) : null}

          {phase === "loading" ? (
            <div className={css.card} role="status" aria-label={t("loading")}>
              <div className={css.statement} data-wash="sky">
                <Skeleton width={56} height={40} />
                <Skeleton lines={3} height={22} />
              </div>
              <div className={css.body}>
                <Skeleton height={64} radius={999} />
              </div>
            </div>
          ) : null}

          {phase === "error" ? (
            <div className={css.card}>
              <div className={css.body}>
                <p className={css.rule}>{t("error")}</p>
                <button type="button" className={css.primary} onClick={() => window.location.reload()}>
                  {t("retry")}
                </button>
              </div>
            </div>
          ) : null}

          {phase === "ask" && deck && card ? (
            <article key={`ask-${card.id}`} className={css.card}>
              <div className={css.statement} data-wash={WASHES[index % WASHES.length]}>
                <div className={css.cardTop}>
                  <span className={css.cardNo}>{pad(card.n)}</span>
                  <span className={css.cardOf}>{t("card", { n: card.n, total: deck.total })}</span>
                </div>
                <p className={css.myth}>{card.myth}</p>
              </div>
              <div className={css.body}>
                <p className={css.ask}>{t("ask")}</p>
                <div className={css.answers}>
                  {deck.choices.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className={css.answer}
                      data-choice={c.id}
                      aria-pressed={choosing === c.id}
                      disabled={busy}
                      onClick={() => void choose(c.id)}
                    >
                      <span className={css.answerIcon} aria-hidden="true">
                        {c.id === "fair" ? <CheckIcon /> : <CrossIcon />}
                      </span>
                      {c.label}
                    </button>
                  ))}
                </div>
                <p className={css.disclaimer}>{card.disclaimer}</p>
              </div>
            </article>
          ) : null}

          {phase === "reveal" && deck && reveal ? (
            <article key={`reveal-${reveal.id}`} className={css.card}>
              <div className={css.statement} data-wash={WASHES[index % WASHES.length]} data-compact="true">
                <div className={css.cardTop}>
                  <span className={css.cardNo}>{pad(reveal.n)}</span>
                  <span className={css.cardOf}>{t("card", { n: reveal.n, total: deck.total })}</span>
                </div>
                <p className={css.mythSmall}>{reveal.myth}</p>
              </div>
              <div className={css.body}>
                <div className={css.verdictRow}>
                  {reveal.feedback ? (
                    <span className={css.verdict} data-ok={reveal.correct === true}>
                      {reveal.correct ? <CheckIcon /> : <CrossIcon />} {reveal.feedback}
                    </span>
                  ) : null}
                  <span className={css.answerLabel}>{t("answer")}</span>
                </div>
                <p className={css.answerBig}>{reveal.answer_label}</p>
                <p className={css.rule}>{reveal.rule}</p>
                <p className={css.detail}>{reveal.detail}</p>
                {reveal.audio_url ? (
                  <div>
                    <PlayButton
                      state={player.state}
                      active={player.isCurrent(reveal.audio_url)}
                      progress={player.progress}
                      onClick={() => void player.toggle(reveal.audio_url)}
                      label={t("listen")}
                    />
                  </div>
                ) : null}
                <div className={css.cite}>
                  <span className={css.citeMark} aria-hidden="true">
                    §
                  </span>
                  <div className={css.citeBody}>
                    <p className={css.citeSection} lang="en">
                      {reveal.section}
                      {reveal.is_estimate ? <span className={css.estimate}> · {t("estimate")}</span> : null}
                    </p>
                    <p className={css.citeSource}>{reveal.source}</p>
                    <a href={reveal.source_url} target="_blank" rel="noopener noreferrer" className={css.citeLink}>
                      {t("open_source")} <ArrowRightIcon />
                    </a>
                  </div>
                </div>
                <button type="button" className={css.primary} disabled={busy} onClick={() => void next()}>
                  {isLast ? t("finish") : t("next")} <ArrowRightIcon />
                </button>
                <p className={css.disclaimer}>{reveal.disclaimer}</p>
              </div>
            </article>
          ) : null}

          {phase === "score" && result ? (
            <article key="score" className={css.card} data-score="true">
              <div className={css.scorePanel}>
                <Illustration name="handshake" className={css.scoreArt} />
                <div className={css.cardTop}>
                  <span className={css.scoreBrand} lang="en">
                    <LogoMark size={20} /> {t("tag")}
                  </span>
                  <span className={css.cardOf}>{t("your_score")}</span>
                </div>
                <p className={css.score} aria-label={result.headline}>
                  <span>{result.score}</span>
                  <span className={css.scoreOf}>/{result.total}</span>
                </p>
                <div className={css.dots} aria-hidden="true">
                  {result.results.map((r) => (
                    <span key={r.id} data-ok={r.correct === true ? "true" : r.correct === false ? "false" : "none"}>
                      {r.correct ? <CheckIcon /> : <CrossIcon />}
                    </span>
                  ))}
                </div>
                <p className={css.message}>{result.message}</p>
              </div>
              <div className={css.body}>
                <div className={css.scoreActions}>
                  <button type="button" className={css.primary} onClick={() => void share()}>
                    <ShareIcon /> {t("share")}
                  </button>
                  <Link href={result.check_url} className={css.secondary}>
                    {result.check_label} <ArrowRightIcon />
                  </Link>
                </div>
                {shareNote ? (
                  <p role="status" className={css.note}>
                    {shareNote}
                  </p>
                ) : null}
                <div className={css.review}>
                  <p className={css.reviewTitle}>{t("review")}</p>
                  <ol className={css.reviewList}>
                    {result.results.map((r) => (
                      <li key={r.id} data-ok={r.correct === true}>
                        <span className={css.reviewMark} aria-hidden="true">
                          {r.correct ? <CheckIcon /> : <CrossIcon />}
                        </span>
                        <span className={css.reviewBody}>
                          <span className={css.reviewMyth}>{r.myth}</span>
                          <span className={css.reviewMeta}>
                            {r.answer_label} · <span lang="en">{r.section}</span>
                          </span>
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
                <button type="button" className={css.ghost} onClick={restart}>
                  {t("again")}
                </button>
                <p className={css.disclaimer}>{result.disclaimer}</p>
              </div>
            </article>
          ) : null}
        </section>
      </div>
    </main>
  );
}
