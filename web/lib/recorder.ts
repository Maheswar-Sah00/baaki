"use client";

// Microphone recording hook (MediaRecorder). Adapted from Deposit Wapas HoldToTalk, with the UI
// removed so any design can sit on top: call start()/stop(), read `state`, `level`, `elapsedMs`.

import { useCallback, useEffect, useRef, useState } from "react";

export type Recording = {
  blob: Blob;
  mimeType: string;
  filename: string;
  durationMs: number;
};

export type RecorderState = "idle" | "starting" | "recording";

// Android Chrome records WebM/Opus (or MP4); iPhone Safari records MP4/AAC. The backend accepts all.
const RECORDER_MIMES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"];

export function pickRecorderMime(): string {
  if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") return "";
  return RECORDER_MIMES.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

export function extForMime(mime: string): string {
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("mp4") || mime.includes("aac")) return "m4a";
  if (mime.includes("mpeg")) return "mp3";
  return "webm";
}

function micErrorMessage(err: unknown): string {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError") return "Microphone blocked. Allow mic access for this site, then try again.";
  if (name === "NotFoundError") return "No microphone found on this device.";
  return err instanceof Error ? err.message : String(err);
}

export function useRecorder({
  onRecorded,
  maxMs = 60_000,
  minMs = 450,
}: {
  onRecorded: (r: Recording) => void;
  maxMs?: number;
  minMs?: number;
}) {
  const [state, setState] = useState<RecorderState>("idle");
  const [level, setLevel] = useState(0); // 0..1 live input level
  const [elapsedMs, setElapsedMs] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onRecordedRef = useRef(onRecorded);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    onRecordedRef.current = onRecorded;
  }, [onRecorded]);

  const stopMeter = () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    setLevel(0);
  };

  const releaseMic = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    analyserRef.current = null;
  };

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") {
        rec.onstop = null;
        rec.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      void ctxRef.current?.close().catch(() => undefined);
    };
  }, []);

  const startMeter = () => {
    const analyser = analyserRef.current;
    const buf = analyser ? new Float32Array(analyser.fftSize) : null;
    let smooth = 0;
    const tick = () => {
      if (analyser && buf) {
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
        const rms = Math.sqrt(sum / buf.length);
        smooth = smooth * 0.6 + Math.min(1, Math.pow(rms * 6, 0.8)) * 0.4;
        setLevel(smooth);
      }
      setElapsedMs(performance.now() - startRef.current);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  const ensureStream = async (): Promise<MediaStream> => {
    const live = streamRef.current?.getAudioTracks().some((t) => t.readyState === "live");
    if (streamRef.current && live) return streamRef.current;
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("This browser cannot record audio here (needs HTTPS and a modern browser).");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    streamRef.current = stream;
    try {
      const Ctx =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (Ctx) {
        const ctx = ctxRef.current ?? new Ctx();
        ctxRef.current = ctx;
        if (ctx.state === "suspended") await ctx.resume().catch(() => undefined);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        ctx.createMediaStreamSource(stream).connect(analyser);
        analyserRef.current = analyser;
      }
    } catch {
      analyserRef.current = null; // the meter is cosmetic; recording still works
    }
    return stream;
  };

  const stop = useCallback(() => {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    const rec = recorderRef.current;
    recorderRef.current = null;
    if (rec && rec.state !== "inactive") rec.stop();
  }, []);

  const start = useCallback(async () => {
    if (recorderRef.current) return;
    setError(null);
    setState("starting");
    let stream: MediaStream;
    try {
      stream = await ensureStream();
    } catch (err) {
      setState("idle");
      setError(micErrorMessage(err));
      return;
    }
    const mime = pickRecorderMime();
    let rec: MediaRecorder;
    try {
      rec = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 64_000 } : undefined);
    } catch (err) {
      setState("idle");
      setError(`Recorder failed: ${err instanceof Error ? err.message : String(err)}`);
      return;
    }
    chunksRef.current = [];
    rec.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
    };
    rec.onstop = () => {
      const durationMs = performance.now() - startRef.current;
      const type = rec.mimeType || mime || "audio/webm";
      const blob = new Blob(chunksRef.current, { type });
      stopMeter();
      releaseMic(); // turn the mic indicator off between recordings
      setState("idle");
      if (durationMs < minMs || blob.size === 0) {
        setError("Too short. Speak a little longer.");
        return;
      }
      onRecordedRef.current({ blob, mimeType: type, filename: `recording.${extForMime(type)}`, durationMs });
    };
    recorderRef.current = rec;
    startRef.current = performance.now();
    rec.start(250);
    setElapsedMs(0);
    setState("recording");
    startMeter();
    timeoutRef.current = window.setTimeout(stop, maxMs);
  }, [maxMs, minMs, stop]);

  const toggle = useCallback(() => {
    if (recorderRef.current) stop();
    else void start();
  }, [start, stop]);

  return { state, level, elapsedMs, error, start, stop, toggle };
}

export function formatTimer(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
