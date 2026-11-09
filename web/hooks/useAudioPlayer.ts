"use client";

// One shared <audio> element per hook: play a URL or a Blob, track progress, and survive autoplay
// blocks (state "blocked": show a big play button; the next tap plays).

import { useCallback, useEffect, useRef, useState } from "react";
import { blobUrl } from "@/lib/blob-url";

export type PlayerState = "idle" | "loading" | "playing" | "paused" | "ended" | "blocked" | "error";

export function useAudioPlayer() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [state, setState] = useState<PlayerState>("idle");
  const [src, setSrc] = useState<string | null>(null);
  const [progress, setProgress] = useState(0); // 0..1
  const [duration, setDuration] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ensure = useCallback((): HTMLAudioElement => {
    if (audioRef.current) return audioRef.current;
    const a = new Audio();
    a.preload = "auto";
    a.addEventListener("playing", () => setState("playing"));
    a.addEventListener("pause", () => setState((s) => (s === "ended" ? s : "paused")));
    a.addEventListener("ended", () => {
      setState("ended");
      setProgress(1);
    });
    a.addEventListener("waiting", () => setState("loading"));
    a.addEventListener("loadedmetadata", () => setDuration(Number.isFinite(a.duration) ? a.duration : null));
    a.addEventListener("timeupdate", () => {
      if (a.duration && Number.isFinite(a.duration)) setProgress(a.currentTime / a.duration);
    });
    a.addEventListener("error", () => {
      setState("error");
      setError("audio_failed");
    });
    audioRef.current = a;
    return a;
  }, []);

  useEffect(() => {
    return () => {
      const a = audioRef.current;
      if (a) {
        a.pause();
        a.removeAttribute("src");
        a.load();
      }
    };
  }, []);

  /** Play from the start. Resolves true if playback started; false if blocked or failed. */
  const play = useCallback(
    async (source: string | Blob | null | undefined): Promise<boolean> => {
      if (!source) return false;
      const a = ensure();
      const url = typeof source === "string" ? source : blobUrl(source);
      setError(null);
      if (a.src !== new URL(url, window.location.href).href) {
        a.src = url;
        setDuration(null);
      }
      a.currentTime = 0;
      setSrc(url);
      setProgress(0);
      setState("loading");
      try {
        await a.play();
        return true;
      } catch (err) {
        const name = err instanceof DOMException ? err.name : "";
        if (name === "NotAllowedError") {
          setState("blocked"); // autoplay policy: wait for a tap
        } else if (name !== "AbortError") {
          setState("error");
          setError("audio_failed");
        }
        return false;
      }
    },
    [ensure],
  );

  const pause = useCallback(() => audioRef.current?.pause(), []);

  const resume = useCallback(async () => {
    const a = audioRef.current;
    if (!a || !a.src) return false;
    try {
      await a.play();
      return true;
    } catch {
      setState("error");
      return false;
    }
  }, []);

  const stop = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    a.pause();
    a.currentTime = 0;
    setState("idle");
    setProgress(0);
  }, []);

  /** Tap on a play button: pause if this source is playing, otherwise play / resume it. */
  const toggle = useCallback(
    async (source: string | Blob | null | undefined) => {
      if (!source) return false;
      const url = typeof source === "string" ? source : blobUrl(source);
      if (src === url && state === "playing") {
        pause();
        return false;
      }
      if (src === url && (state === "paused" || state === "blocked")) return resume();
      return play(source);
    },
    [src, state, pause, resume, play],
  );

  return {
    state,
    src,
    progress,
    duration,
    error,
    playing: state === "playing",
    play,
    pause,
    resume,
    stop,
    toggle,
    /** Is this source the one loaded right now? */
    isCurrent: (source: string | null | undefined) => !!source && src === source,
  };
}
