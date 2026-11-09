"use client";

// Baaki shell: one page that proves the voice plumbing. Tap the mic, speak Telugu or Hinglish,
// see the Gnani Prisma transcript, then hear it read back with Gnani Timbre.
// Placeholder UI: the real design replaces this file; the logic lives in lib/recorder.ts and lib/api.ts.

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { errorMessage, getHealth, postStt, postTts, type SttLang, type SttResponse, type TtsLang } from "@/lib/api";
import { formatTimer, useRecorder, type Recording } from "@/lib/recorder";

const LANGS: { value: SttLang; label: string }[] = [
  { value: "te", label: "తెలుగు" },
  { value: "hinglish", label: "Hinglish" },
  { value: "auto", label: "Auto" },
];

/** Speak back in the language that was heard. */
function ttsLangFor(detected: string | null, chosen: SttLang): TtsLang {
  if (detected?.startsWith("te")) return "te-IN";
  if (detected?.startsWith("hi") || detected?.startsWith("en")) return "hi-en";
  return chosen === "te" ? "te-IN" : "hi-en";
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}

export default function Home() {
  const [lang, setLang] = useState<SttLang>("auto");
  const [busy, setBusy] = useState<"stt" | "tts" | null>(null);
  const [stt, setStt] = useState<{ data: SttResponse; ms: number } | null>(null);
  const [text, setText] = useState("");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backend, setBackend] = useState<string>("checking backend…");

  useEffect(() => {
    const ac = new AbortController();
    getHealth(ac.signal)
      .then((h) => setBackend(`backend ok · gnani ${h.gnani ? "on" : "off"} · llm ${h.llm ? h.llm_provider : "off"}`))
      .catch(() => setBackend("backend not reachable"));
    return () => ac.abort();
  }, []);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const onRecorded = useCallback(
    async (r: Recording) => {
      setError(null);
      setBusy("stt");
      try {
        const res = await postStt(r.blob, r.filename, { lang });
        setStt(res);
        setText(res.data.transcript);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setBusy(null);
      }
    },
    [lang],
  );

  const rec = useRecorder({ onRecorded });
  const recording = rec.state === "recording";

  const speak = async () => {
    if (!text.trim()) return;
    setError(null);
    setBusy("tts");
    try {
      const res = await postTts({ text: text.trim(), lang: ttsLangFor(stt?.data.detected_language_code ?? null, lang) });
      setAudioUrl(URL.createObjectURL(res.blob));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const micLabel = recording
    ? `${formatTimer(rec.elapsedMs)} · tap to stop`
    : rec.state === "starting"
      ? "Opening mic…"
      : busy === "stt"
        ? "Listening to what you said…"
        : "Tap and speak";

  return (
    <main className="shell">
      <header>
        <h1 className="brand">Baaki</h1>
        <p className="tagline">Say what you are owed. In Telugu or Hinglish.</p>
        <p className="status">{backend}</p>
      </header>

      <div className="segmented" role="group" aria-label="Language">
        {LANGS.map((l) => (
          <button key={l.value} type="button" aria-pressed={lang === l.value} onClick={() => setLang(l.value)}>
            {l.label}
          </button>
        ))}
      </div>

      <div className="mic-wrap">
        <button
          type="button"
          className="mic"
          data-state={rec.state}
          style={{ "--level": rec.level } as CSSProperties}
          disabled={busy !== null || rec.state === "starting"}
          aria-label={recording ? "Stop recording" : "Start recording"}
          aria-pressed={recording}
          onClick={rec.toggle}
        >
          <MicIcon />
        </button>
      </div>
      <p className="mic-label" aria-live="polite">
        {micLabel}
      </p>

      {rec.error ? <p className="error">{rec.error}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <section className="card" aria-live="polite">
        <h2>Transcript</h2>
        {stt ? (
          <>
            <textarea className="input transcript" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
            <p className="meta">
              {stt.data.detected_language_code ?? "?"} · {stt.data.duration_s.toFixed(1)} s audio · {stt.ms} ms · {stt.data.model}
            </p>
          </>
        ) : (
          <p className="meta">Your words will appear here.</p>
        )}
      </section>

      <section className="card">
        <h2>Read back</h2>
        <div className="row">
          <button type="button" className="btn" disabled={!text.trim() || busy !== null} onClick={speak}>
            {busy === "tts" ? "Making audio…" : "Play it back"}
          </button>
        </div>
        {audioUrl ? <audio src={audioUrl} controls autoPlay /> : null}
      </section>

      <p className="footnote">Prototype · synthetic data only · not legal advice</p>
    </main>
  );
}
