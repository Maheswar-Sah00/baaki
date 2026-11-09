"use client";

// Record → POST /api/cases/listen → transcript + meter + safety.
// Each /listen call spends one Gnani STT call (the account allows one active request, and the backend
// queues behind a global lock). Interim chunks are OFF by default: pass `interimMs` (e.g. 4500) to send
// the audio-so-far while she is still talking, so the meter moves live. Each interim call re-transcribes
// everything recorded so far, so it costs credits; the final call on stop always happens.

import { useCallback, useEffect, useEffectEvent, useRef, useState } from "react";
import { errorMessage, isAbort, isVoiceServiceError, listen } from "@/lib/api";
import { useRecorder, type Recording } from "@/lib/recorder";
import type { ListenLang, ListenResponse, Safety } from "@/lib/types";

export type ListenStatus = "idle" | "starting" | "recording" | "listening" | "done" | "error";

export function useListen(opts: {
  lang: ListenLang;
  onResult?: (r: ListenResponse, info: { final: boolean }) => void;
  onSafety?: (s: Safety) => void;
  interimMs?: number | null;
  useLlm?: boolean;
  maxMs?: number;
}) {
  const { lang, interimMs = null, useLlm = true, maxMs = 120_000 } = opts;
  const [result, setResult] = useState<ListenResponse | null>(null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceDown, setVoiceDown] = useState(false);
  const [interimCount, setInterimCount] = useState(0);
  const seqRef = useRef(0);
  const interimBusy = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  const callbacks = useRef({ onResult: opts.onResult, onSafety: opts.onSafety });
  useEffect(() => {
    callbacks.current = { onResult: opts.onResult, onSafety: opts.onSafety };
  });
  const emitResult = useCallback((r: ListenResponse, final: boolean) => {
    callbacks.current.onResult?.(r, { final });
    if (r.safety?.flagged) callbacks.current.onSafety?.(r.safety);
  }, []);

  const send = useCallback(
    async (rec: Recording, final: boolean) => {
      const seq = ++seqRef.current;
      if (final) {
        abortRef.current?.abort();
        setListening(true);
        setError(null);
      }
      const ac = new AbortController();
      if (final) abortRef.current = ac;
      try {
        const r = await listen(rec.blob, { lang, useLlm, filename: rec.filename }, ac.signal);
        if (seq !== seqRef.current && !final) return; // a newer call (or the final one) superseded it
        setResult(r);
        setVoiceDown(false);
        emitResult(r, final);
      } catch (err) {
        if (isAbort(err)) return;
        if (final) {
          setError(errorMessage(err));
          setVoiceDown(isVoiceServiceError(err));
        }
      } finally {
        if (final) setListening(false);
      }
    },
    [emitResult, lang, useLlm],
  );

  const rec = useRecorder({ onRecorded: (r) => void send(r, true), maxMs });

  // Interim chunks while recording (opt-in).
  const sendInterim = useEffectEvent(async () => {
    if (interimBusy.current) return;
    const snap = rec.snapshot();
    if (!snap || snap.durationMs < 2500) return;
    interimBusy.current = true;
    setInterimCount((n) => n + 1);
    try {
      await send(snap, false);
    } finally {
      interimBusy.current = false;
    }
  });

  useEffect(() => {
    if (rec.state !== "recording" || !interimMs) return;
    const id = window.setInterval(() => void sendInterim(), interimMs);
    return () => window.clearInterval(id);
  }, [rec.state, interimMs]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    seqRef.current++;
    setResult(null);
    setError(null);
    setListening(false);
    rec.clearError();
  }, [rec]);

  const status: ListenStatus =
    rec.state === "recording"
      ? "recording"
      : rec.state === "starting"
        ? "starting"
        : listening
          ? "listening"
          : error
            ? "error"
            : result
              ? "done"
              : "idle";

  return {
    status,
    result,
    transcript: result?.transcript ?? "",
    detectedLang: result?.detected_language_code ?? null,
    safety: result?.safety ?? null,
    error: error ?? rec.error,
    /** Gnani is busy or down: offer typing instead. */
    voiceDown,
    interimCount,
    recorder: rec,
    level: rec.level,
    elapsedMs: rec.elapsedMs,
    start: rec.start,
    stop: rec.stop,
    toggle: rec.toggle,
    reset,
  };
}
