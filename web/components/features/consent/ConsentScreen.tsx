"use client";

// G13 "Her spoken consent IS the voice sample" (/voice/consent?worker=1&lang=te-IN).
// 1. Baaki reads the consent sentence slowly (Timbre, cached). 2. She repeats it (10-20 s).
// 3. Prisma checks it is the consent sentence; words turn green / grey.
// 4. Heard -> voice profile made from the same recording + consent in her diary.
//    Not heard -> retry, or "confirm by tap" (logged as consent by tap). Never a dead end.
// Plain and functional on purpose: the design session restyles it later.

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useSettings } from "@/hooks";
import { errorMessage } from "@/lib/api";
import { formatTimer, useRecorder, type Recording } from "@/lib/recorder";
import {
  CONSENT_LANGS,
  getConsent,
  getPrompt,
  sendAttempt,
  withdrawConsent,
  type AttemptResult,
  type ConsentLang,
  type ConsentStatus,
  type ConsentWord,
} from "@/lib/features/consent";
import { ConsentWords } from "./ConsentWords";

const css = {
  page: { maxWidth: 560, margin: "0 auto", padding: "var(--s-5, 20px) var(--s-4, 16px) 96px", color: "var(--text)" } as CSSProperties,
  card: {
    background: "var(--surface)",
    border: "1px solid var(--line)",
    borderRadius: "var(--r-lg, 16px)",
    padding: "var(--s-4, 16px)",
    margin: "var(--s-3, 12px) 0",
  } as CSSProperties,
  row: { display: "flex", flexWrap: "wrap", gap: "var(--s-2, 8px)", alignItems: "center" } as CSSProperties,
  btn: {
    minHeight: "var(--tap-min, 48px)",
    padding: "0 18px",
    borderRadius: "var(--r-pill, 999px)",
    border: "1px solid var(--line-2, var(--line))",
    background: "var(--surface-2, var(--surface))",
    color: "var(--text)",
    fontWeight: 600,
    fontSize: "1rem",
    cursor: "pointer",
  } as CSSProperties,
  primary: { background: "var(--accent)", color: "var(--accent-ink, #fff)", border: "1px solid var(--accent)" } as CSSProperties,
  rec: { background: "var(--recording, var(--error))", color: "#fff", border: "1px solid transparent" } as CSSProperties,
  muted: { color: "var(--muted)", fontSize: "0.92rem" } as CSSProperties,
  ok: { color: "var(--success-ink, var(--success))", fontWeight: 800, fontSize: "1.3rem" } as CSSProperties,
  warn: { color: "var(--warn)", fontWeight: 700 } as CSSProperties,
  err: { color: "var(--error)" } as CSSProperties,
  meter: { height: 6, borderRadius: 3, background: "var(--line)", overflow: "hidden", flex: 1, minWidth: 80 } as CSSProperties,
};

type Phase = "idle" | "sending" | "result";
const EXPECTED_S = 14; // a slow reading of the sentence; guides the karaoke cursor while she records

function workerFromQuery(): { worker: number | null; lang: ConsentLang | null } {
  if (typeof window === "undefined") return { worker: null, lang: null };
  const q = new URLSearchParams(window.location.search);
  const n = Number(q.get("worker"));
  const l = q.get("lang");
  const lang = l === "te-IN" || l === "hi-en" || l === "en" ? l : l === "te" ? "te-IN" : l === "hi" || l === "hinglish" ? "hi-en" : null;
  return { worker: Number.isInteger(n) && n > 0 ? n : null, lang };
}

export function ConsentScreen() {
  const settings = useSettings();
  // Read ?worker=&lang= after hydration (the server render has no query), then fall back to settings.
  const [override, setOverride] = useState<{ worker: number | null; lang: ConsentLang | null } | null>(null);
  const [lang, setLang] = useState<ConsentLang | null>(null);
  useEffect(() => {
    const q = workerFromQuery();
    setOverride(q);
    if (q.lang) setLang(q.lang);
  }, []);
  const workerId = override === null || !settings.hydrated ? null : (override.worker ?? settings.workerId);
  const [status, setStatus] = useState<ConsentStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRec, setLastRec] = useState<Recording | null>(null);
  const [promptBusy, setPromptBusy] = useState(false);
  const [promptPos, setPromptPos] = useState<number | null>(null); // 0..1 while the prompt plays
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const refresh = useCallback(
    async (l: ConsentLang | null) => {
      if (workerId === null) return;
      try {
        const s = await getConsent(workerId, l);
        setStatus(s);
        setLoadError(null);
      } catch (e) {
        setLoadError(errorMessage(e));
      }
    },
    [workerId],
  );

  useEffect(() => {
    void refresh(lang);
  }, [refresh, lang]);

  useEffect(() => () => audioRef.current?.pause(), []);

  const submit = useCallback(
    async (rec: Recording, method: "spoken" | "tap") => {
      if (workerId === null) return;
      setPhase("sending");
      setError(null);
      try {
        const r = await sendAttempt(workerId, rec.blob, { lang: status?.lang ?? lang, method, filename: rec.filename });
        setResult(r);
        setPhase("result");
        if (r.status === "ready") void refresh(lang);
      } catch (e) {
        setError(errorMessage(e));
        setPhase(result ? "result" : "idle");
      }
    },
    [workerId, status?.lang, lang, refresh, result],
  );

  const onRecorded = useCallback(
    (rec: Recording) => {
      setLastRec(rec);
      void submit(rec, "spoken");
    },
    [submit],
  );

  const recorder = useRecorder({ onRecorded, maxMs: 25_000, minMs: 1_000 });
  const recording = recorder.state === "recording";

  const playPrompt = useCallback(async () => {
    if (workerId === null) return;
    setPromptBusy(true);
    setError(null);
    try {
      const p = status?.prompt?.audio_url ? status.prompt : await getPrompt(workerId, status?.lang ?? lang);
      if (!p.audio_url) {
        setError("Baaki cannot speak right now. Read the sentence on the screen.");
        return;
      }
      audioRef.current?.pause();
      const a = new Audio(p.audio_url);
      audioRef.current = a;
      a.ontimeupdate = () => setPromptPos(a.duration ? a.currentTime / a.duration : null);
      a.onended = () => setPromptPos(null);
      await a.play();
      if (!status?.prompt?.audio_url) void refresh(lang);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPromptBusy(false);
    }
  }, [workerId, status, lang, refresh]);

  const withdraw = useCallback(async () => {
    if (workerId === null) return;
    setError(null);
    try {
      await withdrawConsent(workerId);
      setResult(null);
      setLastRec(null);
      setPhase("idle");
      await refresh(lang);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [workerId, lang, refresh]);

  const retry = useCallback(() => {
    setResult(null);
    setPhase("idle");
    recorder.clearError();
  }, [recorder]);

  const baseWords: ConsentWord[] = useMemo(() => result?.words ?? status?.words ?? [], [result, status]);

  // Karaoke cursor: follows the prompt while it plays, then the recording timer.
  const cursor = useMemo(() => {
    if (!baseWords.length) return null;
    const frac = promptPos ?? (recording ? Math.min(0.999, recorder.elapsedMs / 1000 / EXPECTED_S) : null);
    return frac === null ? null : Math.floor(frac * baseWords.length);
  }, [baseWords.length, promptPos, recording, recorder.elapsedMs]);

  if (workerId === null) return <main style={css.page}>Loading...</main>;

  const ready = result?.status === "ready";
  const notMatched = result?.status === "not_matched";
  const tooShortOrLong = result?.status === "too_short" || result?.status === "too_long";
  const active = !!status?.consent_active && !result;
  const minS = status?.duration_hint_s?.[0] ?? 10;

  return (
    <main style={css.page}>
      <p style={css.muted}>
        <Link href="/voice">← My voice</Link>
      </p>
      <h1 style={{ fontSize: "1.6rem", margin: "8px 0" }}>Your voice, your permission</h1>
      <p style={css.muted}>
        Say this sentence after Baaki. The same recording is your permission and your voice sample. Baaki keeps only the
        voice profile and a fingerprint (hash) of the recording, never the recording.
      </p>

      <div style={css.row}>
        {CONSENT_LANGS.map((l) => (
          <button
            key={l.id}
            type="button"
            style={{ ...css.btn, ...(status?.lang === l.id ? css.primary : null) }}
            aria-pressed={status?.lang === l.id}
            onClick={() => {
              setLang(l.id);
              setResult(null);
              setPhase("idle");
            }}
          >
            {l.label}
          </button>
        ))}
      </div>

      {loadError && <p style={css.err}>{loadError}</p>}

      {status && (
        <section style={css.card}>
          <ConsentWords words={baseWords} cursor={cursor} />
          {status.lang !== "en" && <p style={css.muted}>{status.meaning_en}</p>}
          <div style={css.row}>
            <button type="button" style={css.btn} onClick={playPrompt} disabled={promptBusy || recording}>
              {promptBusy ? "Loading..." : "▶ Listen first"}
            </button>
          </div>
        </section>
      )}

      {active && (
        <section style={css.card}>
          <p style={css.ok}>✓ Voice profile ready</p>
          <p style={css.muted}>
            Consent {status?.log.at(-1)?.consent_method === "tap" ? "confirmed by tap" : "given by voice"} on{" "}
            {status?.log.at(-1)?.timestamp.slice(0, 16).replace("T", " ")} UTC.
          </p>
        </section>
      )}

      {status && !ready && (
        <section style={css.card}>
          <div style={css.row}>
            <button
              type="button"
              style={{ ...css.btn, ...(recording ? css.rec : css.primary) }}
              onClick={recorder.toggle}
              disabled={phase === "sending"}
            >
              {recording ? `■ Stop (${formatTimer(recorder.elapsedMs)})` : active ? "● Record again" : "● Record"}
            </button>
            {recording && (
              <div style={css.meter} aria-hidden>
                <div style={{ width: `${Math.round(recorder.level * 100)}%`, height: "100%", background: "var(--accent)" }} />
              </div>
            )}
          </div>
          {recording && recorder.elapsedMs < minS * 1000 && (
            <p style={css.muted}>Keep reading, at least {minS} seconds.</p>
          )}
          {phase === "sending" && <p style={css.muted}>Checking your words...</p>}
          {recorder.error && <p style={css.err}>{recorder.error}</p>}
        </section>
      )}

      {result && phase === "result" && (
        <section style={css.card} aria-live="polite">
          {ready && (
            <>
              <p style={css.ok}>{result.consent_method === "tap" ? "✓ Consent confirmed by tap" : "✓ Consent heard"}</p>
              <p>Your voice profile is ready. Messages to employers can now use your voice, and each one says first that it is an AI message.</p>
              {result.match && (
                <p style={css.muted}>
                  {result.match.content_matched} of {result.match.content_total} words heard.
                </p>
              )}
              <p style={css.muted}>Saved in your diary: {result.consent?.timestamp.slice(0, 19).replace("T", " ")} UTC, hash {result.consent?.hash.slice(0, 12)}…</p>
            </>
          )}

          {notMatched && (
            <>
              <p style={css.warn}>{result.message}</p>
              {result.match && (
                <p style={css.muted}>
                  {result.match.content_matched} of {result.match.content_total} words heard
                  {!result.match.name_matched ? ", your name was not heard" : ""}.
                </p>
              )}
              {!!result.missed?.length && <p style={css.muted}>Missed: {result.missed.join(", ")}</p>}
              {result.transcript && <p style={css.muted}>Baaki heard: “{result.transcript}”</p>}
              <div style={css.row}>
                <button type="button" style={{ ...css.btn, ...css.primary }} onClick={retry}>
                  Try again
                </button>
                <button
                  type="button"
                  style={css.btn}
                  disabled={!lastRec}
                  onClick={() => lastRec && void submit(lastRec, "tap")}
                >
                  I agree, confirm by tap
                </button>
              </div>
            </>
          )}

          {tooShortOrLong && (
            <>
              <p style={css.warn}>{result.message}</p>
              <button type="button" style={{ ...css.btn, ...css.primary }} onClick={retry}>
                Record again
              </button>
            </>
          )}
        </section>
      )}

      {error && <p style={css.err}>{error}</p>}

      {(status?.profile.exists || ready) && (
        <section style={css.card}>
          <p style={css.muted}>You can take back your permission at any time. This deletes your voice profile.</p>
          <button type="button" style={css.btn} onClick={withdraw}>
            Withdraw consent and delete my voice
          </button>
        </section>
      )}

      {!!status?.log.length && (
        <details style={css.card}>
          <summary>Consent record ({status.log.length})</summary>
          <ul style={{ paddingLeft: 18 }}>
            {status.log.map((e) => (
              <li key={e.diary_entry_id} style={css.muted}>
                {e.timestamp.slice(0, 16).replace("T", " ")} · {e.event === "withdrawn" ? "withdrawn" : `given (${e.consent_method})`} ·{" "}
                {e.hash.slice(0, 10)}…
              </li>
            ))}
          </ul>
        </details>
      )}
    </main>
  );
}
