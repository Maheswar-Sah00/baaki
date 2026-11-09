"use client";

// Fair or Not? (V08): five myth cards for employers. Functional only; styling is left to the design session.
// One card at a time: tap Fair / Not fair -> the rule with its section and source -> next -> score card.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
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

const LANG_KEY = "baaki.quiz.lang";

const s: Record<string, CSSProperties> = {
  page: {
    minHeight: "100dvh",
    background: "var(--bg)",
    color: "var(--text)",
    fontFamily: "var(--font-sans)",
    padding: "var(--s-6) var(--space) var(--s-9)",
  },
  col: { maxWidth: "var(--shell)", margin: "0 auto", display: "grid", gap: "var(--s-5)" },
  kicker: { color: "var(--muted)", fontSize: 14, margin: 0 },
  h1: { fontFamily: "var(--font-display)", fontSize: 32, lineHeight: 1.1, margin: 0 },
  intro: { color: "var(--text-2)", margin: 0, lineHeight: 1.5 },
  langs: { display: "flex", gap: "var(--s-2)", flexWrap: "wrap" },
  card: {
    background: "var(--surface)",
    border: "1px solid var(--line)",
    borderRadius: "var(--r-lg)",
    boxShadow: "var(--shadow-1)",
    padding: "var(--s-6)",
    display: "grid",
    gap: "var(--s-4)",
  },
  count: { color: "var(--muted)", fontSize: 13, margin: 0 },
  myth: { fontSize: 22, lineHeight: 1.35, fontWeight: 600, margin: 0 },
  row: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--s-3)" },
  verdict: { fontSize: 20, fontWeight: 700, margin: 0 },
  rule: { fontSize: 17, lineHeight: 1.5, margin: 0 },
  detail: { color: "var(--text-2)", lineHeight: 1.5, margin: 0 },
  cite: {
    background: "var(--surface-2)",
    borderRadius: "var(--r-sm)",
    padding: "var(--s-3) var(--s-4)",
    fontSize: 13,
    lineHeight: 1.45,
    color: "var(--text-2)",
    display: "grid",
    gap: "var(--s-1)",
  },
  disclaimer: { color: "var(--muted)", fontSize: 12, lineHeight: 1.4, margin: 0 },
  score: { fontFamily: "var(--font-display)", fontSize: 64, fontWeight: 800, margin: 0, lineHeight: 1 },
  link: { color: "var(--accent-text)", fontWeight: 600 },
  list: { margin: 0, paddingLeft: "var(--s-5)", display: "grid", gap: "var(--s-2)", lineHeight: 1.45 },
};

function btn(kind: "primary" | "ghost" | "chip", active = false): CSSProperties {
  const base: CSSProperties = {
    minHeight: kind === "chip" ? "var(--tap-min)" : "var(--tap)",
    borderRadius: kind === "chip" ? "var(--r-pill)" : "var(--r-md)",
    padding: kind === "chip" ? "0 var(--s-4)" : "0 var(--s-5)",
    font: "inherit",
    fontWeight: 600,
    fontSize: kind === "chip" ? 14 : 17,
    cursor: "pointer",
    border: "1px solid var(--line-2)",
    background: "var(--surface)",
    color: "var(--text)",
  };
  if (kind === "primary" || active) {
    return { ...base, background: "var(--accent)", color: "var(--accent-ink)", borderColor: "var(--accent)" };
  }
  return base;
}

type Phase = "loading" | "ask" | "reveal" | "score" | "error";

export function FairOrNot() {
  const [lang, setLang] = useState<QuizLang>("en");
  const [deck, setDeck] = useState<QuizDeck | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, QuizChoice>>({});
  const [reveal, setReveal] = useState<QuizReveal | null>(null);
  const [result, setResult] = useState<QuizScore | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [busy, setBusy] = useState(false);
  const [shareNote, setShareNote] = useState<string | null>(null);
  const t = makeT(lang);
  const firstLoad = useRef(true);

  // Remember the language per viewer (a convenience only; the page works without storage).
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LANG_KEY) as QuizLang | null;
      if (saved && LANG_OPTIONS.some((o) => o.id === saved)) setLang(saved);
    } catch {
      /* storage blocked */
    }
  }, []);

  // Load the deck for the language; keep progress, and re-fetch what is on screen in the new language.
  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      try {
        const d = await getDeck(lang, ac.signal);
        setDeck(d);
        if (firstLoad.current) {
          firstLoad.current = false;
          setPhase("ask");
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) setPhase("error");
      }
    })();
    return () => ac.abort();
  }, [lang]);

  useEffect(() => {
    // Re-translate a shown answer or score after a language switch.
    if (phase === "reveal" && reveal && reveal.choice) {
      answerCard(reveal.id, reveal.choice, lang).then(setReveal).catch(() => undefined);
    } else if (phase === "score" && result) {
      scoreQuiz(answers, lang).then(setResult).catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const pickLang = (l: QuizLang) => {
    setLang(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      /* storage blocked */
    }
  };

  const card = deck?.cards[index] ?? null;
  const isLast = deck ? index >= deck.total - 1 : false;

  const choose = useCallback(
    async (choice: QuizChoice) => {
      if (!card || busy) return;
      setBusy(true);
      try {
        const r = await answerCard(card.id, choice, lang);
        setAnswers((a) => ({ ...a, [card.id]: choice }));
        setReveal(r);
        setPhase("reveal");
      } catch {
        setPhase("error");
      } finally {
        setBusy(false);
      }
    },
    [card, busy, lang],
  );

  const next = useCallback(async () => {
    if (!deck) return;
    if (!isLast) {
      setIndex((i) => i + 1);
      setReveal(null);
      setPhase("ask");
      return;
    }
    setBusy(true);
    try {
      setResult(await scoreQuiz(answers, lang));
      setPhase("score");
    } catch {
      setPhase("error");
    } finally {
      setBusy(false);
    }
  }, [deck, isLast, answers, lang]);

  const restart = () => {
    setIndex(0);
    setAnswers({});
    setReveal(null);
    setResult(null);
    setShareNote(null);
    setPhase(deck ? "ask" : "loading");
  };

  const share = async () => {
    if (!result) return;
    const url = `${window.location.origin}/quiz`;
    const r = await shareScore(result.share_text, url);
    setShareNote(r === "shared" ? t("shared") : r === "copied" ? t("copied") : r === "failed" ? t("share_failed") : null);
  };

  return (
    <main style={s.page}>
      <div style={s.col}>
        <header style={{ display: "grid", gap: "var(--s-2)" }}>
          <p style={s.kicker}>{t("kicker")}</p>
          <h1 style={s.h1}>{deck?.title ?? "Fair or Not?"}</h1>
          {deck && phase !== "score" && <p style={s.intro}>{deck.intro}</p>}
        </header>

        <div style={s.langs} role="group" aria-label="Language">
          {LANG_OPTIONS.map((o) => (
            <button key={o.id} type="button" style={btn("chip", o.id === lang)} aria-pressed={o.id === lang} onClick={() => pickLang(o.id)}>
              {o.label}
            </button>
          ))}
        </div>

        {phase === "loading" && <p>{t("loading")}</p>}

        {phase === "error" && (
          <section style={s.card}>
            <p>{t("error")}</p>
            <button type="button" style={btn("primary")} onClick={() => window.location.reload()}>
              {t("retry")}
            </button>
          </section>
        )}

        {phase === "ask" && deck && card && (
          <section style={s.card} aria-live="polite">
            <p style={s.count}>{t("card", { n: card.n, total: deck.total })}</p>
            <p style={s.myth}>{card.myth}</p>
            <p style={{ margin: 0, color: "var(--muted)" }}>{t("ask")}</p>
            <div style={s.row}>
              {deck.choices.map((c) => (
                <button key={c.id} type="button" style={btn("ghost")} disabled={busy} onClick={() => choose(c.id)}>
                  {c.label}
                </button>
              ))}
            </div>
            <p style={s.disclaimer}>{card.disclaimer}</p>
          </section>
        )}

        {phase === "reveal" && deck && reveal && (
          <section style={s.card} aria-live="polite">
            <p style={s.count}>{t("card", { n: reveal.n, total: deck.total })}</p>
            <p style={{ ...s.detail, fontStyle: "italic" }}>{reveal.myth}</p>
            <p style={{ ...s.verdict, color: reveal.correct ? "var(--success)" : "var(--accent-text)" }}>
              {reveal.feedback} · {reveal.answer_label}
            </p>
            <p style={s.rule}>{reveal.rule}</p>
            <p style={s.detail}>{reveal.detail}</p>
            {reveal.audio_url && (
              <div style={{ display: "grid", gap: "var(--s-1)" }}>
                <span style={s.count}>{t("listen")}</span>
                <audio controls preload="none" src={reveal.audio_url} style={{ width: "100%" }} />
              </div>
            )}
            <div style={s.cite}>
              <span>
                <strong>{t("section")}:</strong> {reveal.section}
                {reveal.is_estimate && <em style={{ color: "var(--estimate)" }}> · {t("estimate")}</em>}
              </span>
              <span>
                <strong>{t("source")}:</strong> {reveal.source}
              </span>
              <a href={reveal.source_url} target="_blank" rel="noopener noreferrer" style={s.link}>
                {t("open_source")}
              </a>
            </div>
            <p style={s.disclaimer}>{reveal.disclaimer}</p>
            <button type="button" style={btn("primary")} disabled={busy} onClick={next}>
              {isLast ? t("finish") : t("next")}
            </button>
          </section>
        )}

        {phase === "score" && result && (
          <section style={s.card} aria-live="polite">
            <p style={s.count}>{t("your_score")}</p>
            <p style={s.score}>{result.headline}</p>
            <p style={s.rule}>{result.message}</p>
            <Link href={result.check_url} style={{ ...btn("primary"), display: "grid", placeItems: "center", textDecoration: "none" }}>
              {result.check_label}
            </Link>
            <button type="button" style={btn("ghost")} onClick={share}>
              {t("share")}
            </button>
            {shareNote && (
              <p role="status" style={s.count}>
                {shareNote}
              </p>
            )}
            <div style={{ display: "grid", gap: "var(--s-2)" }}>
              <strong>{t("review")}</strong>
              <ol style={s.list}>
                {result.results.map((r) => (
                  <li key={r.id}>
                    <span style={{ color: r.correct ? "var(--success)" : "var(--accent-text)", fontWeight: 600 }}>
                      {r.correct ? "✓" : "✗"} {r.answer_label}
                    </span>{" "}
                    {r.myth} <span style={{ color: "var(--muted)" }}>({r.section})</span>
                  </li>
                ))}
              </ol>
            </div>
            <button type="button" style={btn("ghost")} onClick={restart}>
              {t("again")}
            </button>
            <p style={s.disclaimer}>{result.disclaimer}</p>
          </section>
        )}
      </div>
    </main>
  );
}
