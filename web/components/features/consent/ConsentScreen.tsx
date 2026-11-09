"use client";

// G13 "Her spoken consent IS the voice sample" (/voice/consent?worker=1&lang=te-IN).
// 1. Baaki reads the consent sentence slowly (Timbre, cached). 2. She repeats it (10-20 s).
// 3. Prisma checks it is the consent sentence; the words she said light up in ink, missed words stay grey.
// 4. Heard -> voice profile made from the same recording + consent in her diary.
//    Not heard -> retry, or "confirm by tap" (logged as consent by tap). Never a dead end.

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from "react";
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
import { ErrorNote, Illustration, Loading, Screen, SkeletonCard } from "@/components/ui/primitives";
import { CheckIcon, LockIcon, MicIcon, PlayIcon, StopIcon } from "@/components/ui/icons";
import { ConsentWords } from "./ConsentWords";
import css from "./consent.module.css";

const EXPECTED_S = 14; // a slow reading of the sentence; guides the karaoke cursor while she records
const HTML_LANG: Record<ConsentLang, string> = { "te-IN": "te", "hi-en": "hi", en: "en" };

type Query = { worker: number | null; lang: ConsentLang | null };

function parseQuery(search: string): Query {
  const q = new URLSearchParams(search);
  const n = Number(q.get("worker"));
  const l = q.get("lang");
  const lang = l === "te-IN" || l === "hi-en" || l === "en" ? l : l === "te" ? "te-IN" : l === "hi" || l === "hinglish" ? "hi-en" : null;
  return { worker: Number.isInteger(n) && n > 0 ? n : null, lang };
}

// ?worker=&lang= is read after hydration (the server render has no query): useSyncExternalStore gives null on the
// server and during hydration, then the real query string.
const noSubscribe = () => () => undefined;
const readSearch = () => window.location.search;
const serverSearch = () => null;

export function ConsentScreen() {
  const settings = useSettings();
  const search = useSyncExternalStore(noSubscribe, readSearch, serverSearch);
  const query = useMemo(() => (search === null ? null : parseQuery(search)), [search]);
  const [picked, setPicked] = useState<ConsentLang | null>(null);
  const lang = picked ?? query?.lang ?? null;
  const workerId = query === null || !settings.hydrated ? null : (query.worker ?? settings.workerId);
  const [status, setStatus] = useState<ConsentStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRec, setLastRec] = useState<Recording | null>(null);
  const [promptBusy, setPromptBusy] = useState(false);
  const [promptPos, setPromptPos] = useState<number | null>(null); // 0..1 while the prompt plays
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Load (and reload on a language switch): state is set only when the request settles.
  useEffect(() => {
    if (workerId === null) return;
    const ac = new AbortController();
    getConsent(workerId, lang, ac.signal)
      .then((s) => {
        setStatus(s);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ac.signal.aborted) setLoadError(errorMessage(e));
      });
    return () => ac.abort();
  }, [workerId, lang]);

  /** Re-read the status after an action (event handlers only). */
  const refresh = useCallback(async () => {
    if (workerId === null) return;
    try {
      setStatus(await getConsent(workerId, lang));
      setLoadError(null);
    } catch (e) {
      setLoadError(errorMessage(e));
    }
  }, [workerId, lang]);

  useEffect(() => () => audioRef.current?.pause(), []);

  const statusLang = status?.lang ?? null;
  const submit = async (rec: Recording, method: "spoken" | "tap") => {
    if (workerId === null) return;
    setSending(true);
    setError(null);
    try {
      const r = await sendAttempt(workerId, rec.blob, { lang: statusLang ?? lang, method, filename: rec.filename });
      setResult(r);
      if (r.status === "ready") void refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSending(false);
    }
  };

  const onRecorded = (rec: Recording) => {
    setLastRec(rec);
    void submit(rec, "spoken");
  };

  const recorder = useRecorder({ onRecorded, maxMs: 25_000, minMs: 1_000 });
  const recording = recorder.state === "recording";

  const playPrompt = async () => {
    if (workerId === null) return;
    setPromptBusy(true);
    setError(null);
    try {
      const p = status?.prompt?.audio_url ? status.prompt : await getPrompt(workerId, statusLang ?? lang);
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
      if (!status?.prompt?.audio_url) void refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPromptBusy(false);
    }
  };

  const withdraw = async () => {
    if (workerId === null) return;
    setError(null);
    try {
      await withdrawConsent(workerId);
      setResult(null);
      setLastRec(null);
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const retry = () => {
    setResult(null);
    recorder.clearError();
  };

  const baseWords: ConsentWord[] = useMemo(() => result?.words ?? status?.words ?? [], [result, status]);

  // Karaoke cursor: follows the prompt while it plays, then the recording timer.
  const frac = promptPos ?? (recording ? Math.min(0.999, recorder.elapsedMs / 1000 / EXPECTED_S) : null);
  const cursor = !baseWords.length || frac === null ? null : Math.floor(frac * baseWords.length);

  const ready = result?.status === "ready";
  const notMatched = result?.status === "not_matched";
  const tooShortOrLong = result?.status === "too_short" || result?.status === "too_long";
  const active = !!status?.consent_active && !result;
  const minS = status?.duration_hint_s?.[0] ?? 10;
  const shownLang = status?.lang ?? lang ?? "te-IN";

  return (
    <Screen title="Voice consent" back="/voice" className={`fx ${css.screen}`}>
      <section className={css.hero} data-wash="lilac">
        <div className={css.heroText}>
          <p className="fx-eyebrow fx-wash-ink">Say it once</p>
          <h1 className={`fx-h ${css.title}`}>
            Your voice, <em>your permission.</em>
          </h1>
          <p className={css.heroSub}>Say this sentence after Baaki. The same recording is your permission and your voice sample.</p>
        </div>
        <Illustration name="speak" className={css.heroArt} />
      </section>

      <div className={css.langs} role="group" aria-label="Language">
        {CONSENT_LANGS.map((l) => (
          <button
            key={l.id}
            type="button"
            lang={HTML_LANG[l.id]}
            aria-pressed={shownLang === l.id}
            onClick={() => {
              setPicked(l.id);
              setResult(null);
            }}
          >
            {l.label}
          </button>
        ))}
      </div>

      <ErrorNote message={loadError} />

      {workerId === null || (!status && !loadError) ? (
        <div role="status" aria-label="Loading">
          <SkeletonCard />
        </div>
      ) : null}

      {status ? (
        <section className={css.script} aria-live="polite" lang={HTML_LANG[status.lang]}>
          <p className={css.scriptLabel}>{recording ? "Read it now, slowly" : sending ? "Checking your words…" : "Say this after Baaki"}</p>
          <ConsentWords words={baseWords} cursor={cursor} />
          {!ready ? (
            <div className={css.controls}>
              <button type="button" className={css.listen} onClick={() => void playPrompt()} disabled={promptBusy || recording || sending}>
                <span className={css.listenIcon} aria-hidden="true">
                  <PlayIcon />
                </span>
                {promptBusy ? "Loading…" : "Listen first"}
              </button>
              <button
                type="button"
                className={css.record}
                data-state={recording ? "recording" : "idle"}
                onClick={recorder.toggle}
                disabled={sending}
                aria-pressed={recording}
                style={{ "--level": recorder.level } as CSSProperties}
              >
                <span className={css.recordDot} aria-hidden="true">
                  {recording ? <StopIcon /> : <MicIcon />}
                </span>
                <span className={css.recordText}>
                  {recording ? `Stop · ${formatTimer(recorder.elapsedMs)}` : active ? "Record again" : "Record"}
                </span>
              </button>
            </div>
          ) : null}
          {recording ? (
            <div className={css.minWrap}>
              <span className={css.minBar} aria-hidden="true">
                <span style={{ transform: `scaleX(${Math.min(1, recorder.elapsedMs / (minS * 1000))})` }} />
              </span>
              {recorder.elapsedMs < minS * 1000 ? <span className={css.minText}>Keep reading, at least {minS} seconds.</span> : null}
            </div>
          ) : null}
          {sending ? <Loading label="Checking your words…" /> : null}
          {recorder.error ? <ErrorNote message={recorder.error} /> : null}
          {status.lang !== "en" ? (
            <p className={css.meaning} lang="en">
              {status.meaning_en}
            </p>
          ) : null}
        </section>
      ) : null}

      {active ? (
        <section className={css.panel} data-wash="sage">
          <p className={css.okTitle}>
            <span className={css.okIcon} aria-hidden="true">
              <CheckIcon />
            </span>
            Voice profile ready
          </p>
          <p className={css.panelText}>
            Consent {status?.log.at(-1)?.consent_method === "tap" ? "confirmed by tap" : "given by voice"} on{" "}
            {status?.log.at(-1)?.timestamp.slice(0, 16).replace("T", " ")} UTC.
          </p>
        </section>
      ) : null}

      {result && !sending ? (
        <section className={css.panel} data-wash={ready ? "sage" : "butter"} aria-live="polite">
          {ready ? (
            <>
              <p className={css.okTitle}>
                <span className={css.okIcon} aria-hidden="true">
                  <CheckIcon />
                </span>
                {result.consent_method === "tap" ? "Consent confirmed by tap" : "Consent heard"}
              </p>
              <p className={css.panelText}>
                Your voice profile is ready. Messages to employers can now use your voice, and each one says first that it
                is an AI message.
              </p>
              {result.match ? (
                <p className={css.count}>
                  <b>{result.match.content_matched}</b> of {result.match.content_total} words heard
                </p>
              ) : null}
              <p className={css.hash}>
                Saved in your diary: {result.consent?.timestamp.slice(0, 19).replace("T", " ")} UTC · hash{" "}
                {result.consent?.hash.slice(0, 12)}…
              </p>
            </>
          ) : null}

          {notMatched ? (
            <>
              <p className={css.warnTitle}>{result.message}</p>
              {result.match ? (
                <p className={css.count}>
                  <b>{result.match.content_matched}</b> of {result.match.content_total} words heard
                  {!result.match.name_matched ? ", your name was not heard" : ""}.
                </p>
              ) : null}
              {result.missed?.length ? (
                <p className={css.missed}>
                  Missed:{" "}
                  {result.missed.map((m) => (
                    <span key={m} className="fx-chip" style={{ background: "var(--surface)" }}>
                      {m}
                    </span>
                  ))}
                </p>
              ) : null}
              {result.transcript ? <p className={css.panelText}>Baaki heard: &ldquo;{result.transcript}&rdquo;</p> : null}
              <div className={css.choices}>
                <button type="button" className={css.primary} onClick={retry}>
                  Try again
                </button>
                <button type="button" className={css.secondary} disabled={!lastRec} onClick={() => lastRec && void submit(lastRec, "tap")}>
                  I agree, confirm by tap
                </button>
              </div>
            </>
          ) : null}

          {tooShortOrLong ? (
            <>
              <p className={css.warnTitle}>{result.message}</p>
              <button type="button" className={css.primary} onClick={retry}>
                Record again
              </button>
            </>
          ) : null}
        </section>
      ) : null}

      <ErrorNote message={error} />

      <p className={css.lock}>
        <LockIcon /> Baaki keeps only the voice profile and a fingerprint (hash) of the recording, never the recording.
      </p>

      {status?.profile.exists || ready ? (
        <section className={css.withdraw}>
          <p className="fx-muted">You can take back your permission at any time. This deletes your voice profile.</p>
          <button type="button" className={css.danger} onClick={() => void withdraw()}>
            Withdraw consent and delete my voice
          </button>
        </section>
      ) : null}

      {status?.log.length ? (
        <details className={css.log}>
          <summary>Consent record ({status.log.length})</summary>
          <ul>
            {status.log.map((e) => (
              <li key={e.diary_entry_id}>
                <span>
                  {e.timestamp.slice(0, 16).replace("T", " ")} · {e.event === "withdrawn" ? "withdrawn" : `given (${e.consent_method})`}
                </span>
                <code>{e.hash.slice(0, 10)}…</code>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Screen>
  );
}
