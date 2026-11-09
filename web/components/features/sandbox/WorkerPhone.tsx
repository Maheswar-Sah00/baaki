"use client";

// "Lakshmi's phone": polls the sandbox; when Sharma ji pays it shows "Paisa aa gaya!" and plays the
// cached clip (if the browser blocks autoplay, the player stays visible to tap).

import { useEffect, useRef, useState } from "react";

import { SandboxError, getWorkerPanel, type SandboxWorker } from "@/lib/features/sandbox";

import { Banner, box } from "./Banner";

const POLL_MS = 2500;

export function WorkerPhone({ sid }: { sid: string }) {
  const [data, setData] = useState<SandboxWorker | null>(null);
  const [gone, setGone] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playedFor = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const d = await getWorkerPanel(sid);
        if (!alive) return;
        setData(d);
        if (d.paid) return; // nothing more will change
      } catch (e) {
        if (e instanceof SandboxError && e.gone) {
          if (alive) setGone(e.message);
          return;
        }
      }
      if (alive) timer = setTimeout(tick, POLL_MS);
    };
    void tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [sid]);

  const clip = data?.alert?.audio_url ?? null;
  useEffect(() => {
    if (!clip || playedFor.current === clip || !audioRef.current) return;
    playedFor.current = clip;
    audioRef.current.play().catch(() => undefined);
  }, [clip]);

  return (
    <section style={box} aria-label="Lakshmi's phone" aria-live="polite">
      <h2 style={{ fontSize: 18, margin: "0 0 8px" }}>Lakshmi&apos;s phone</h2>
      <Banner />
      {gone && <p role="alert">{gone}</p>}
      {!gone && !data && <p>Connecting…</p>}
      {data && !data.alert && (
        <>
          <p style={{ fontSize: 15 }}>
            Waiting for {data.employer.name}… Baaki still due: <strong>{data.balance_display}</strong>
          </p>
          <p style={{ fontSize: 13, color: "var(--muted)" }}>
            {data.played ? `${data.employer.name} played your voice note.` : "Voice note sent. Not played yet."}
          </p>
        </>
      )}
      {data?.alert && (
        <div style={{ background: "var(--success-soft)", borderRadius: "var(--r-md, 12px)", padding: 16, marginTop: 8 }}>
          <p style={{ fontSize: 28, fontWeight: 700, margin: 0, color: "var(--success-ink)" }}>{data.alert.headline}</p>
          <p style={{ margin: "4px 0 8px", color: "var(--text-2)" }}>{data.alert.headline_en}</p>
          <p lang="te" style={{ fontSize: 17, margin: "0 0 8px" }}>
            {data.alert.text}
          </p>
          {data.alert.audio_url ? (
            <>
              <audio ref={audioRef} controls preload="auto" src={data.alert.audio_url} style={{ width: "100%" }} />
              <p style={{ fontSize: 13, color: "var(--muted)", margin: "4px 0 0" }}>{data.alert.audio_label}</p>
            </>
          ) : (
            <p style={{ fontSize: 13, color: "var(--muted)" }}>{data.alert.audio_label}</p>
          )}
          <p style={{ fontSize: 15, margin: "8px 0 0" }}>
            Baaki still due: <strong>{data.balance_display}</strong>
          </p>
        </div>
      )}
    </section>
  );
}
