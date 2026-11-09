"use client";

// "Lakshmi's phone": polls the sandbox. While waiting it shows what is still due and whether Sharma ji has played
// the voice note; when he pays it shows "Paisa aa gaya!" and plays the cached clip (a blocked autoplay leaves the
// play button ready to tap).

import { useEffect, useRef, useState } from "react";
import { SandboxError, getWorkerPanel, type SandboxWorker } from "@/lib/features/sandbox";
import { useAudioPlayer } from "@/hooks";
import { Confetti, PlayButton } from "@/components/ui/primitives";
import { CheckIcon, ClockIcon } from "@/components/ui/icons";
import { Banner } from "./Banner";
import css from "./sandbox.module.css";

const POLL_MS = 2500;

export function WorkerPhone({ sid }: { sid: string }) {
  const [data, setData] = useState<SandboxWorker | null>(null);
  const [gone, setGone] = useState<string | null>(null);
  const player = useAudioPlayer();
  const play = player.play;
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
    if (!clip || playedFor.current === clip) return;
    playedFor.current = clip;
    void play(clip);
  }, [clip, play]);

  const employer = data?.employer.name ?? "Sharma ji";
  return (
    <div className={css.app} aria-label="Lakshmi's phone" aria-live="polite">
      <div className={css.appHead}>
        <span className={css.appTitle}>
          <span className={css.live} aria-hidden="true" /> Baaki · బాకీ
        </span>
        <Banner compact />
      </div>

      {gone ? (
        <p role="alert" className={css.error}>
          {gone}
        </p>
      ) : null}
      {!gone && !data ? <p className={css.small}>Connecting…</p> : null}

      {data && !data.alert ? (
        <>
          <section className={css.due}>
            <p className={css.dueLabel}>Baaki still due</p>
            <p className={css.dueValue}>{data.balance_display}</p>
            <p className={css.small}>Waiting for {employer}…</p>
          </section>
          <ol className={css.steps}>
            <li data-done="true">
              <span aria-hidden="true">
                <CheckIcon />
              </span>
              Voice note sent
            </li>
            <li data-done={data.played}>
              <span aria-hidden="true">{data.played ? <CheckIcon /> : <ClockIcon />}</span>
              {data.played ? `${employer} played your voice note.` : "Not played yet."}
            </li>
            <li data-done="false">
              <span aria-hidden="true">
                <ClockIcon />
              </span>
              Payment
            </li>
          </ol>
        </>
      ) : null}

      {data?.alert ? (
        <section className={css.win} data-wash="sage">
          <Confetti pieces={18} />
          <span className={css.winCheck} aria-hidden="true">
            <CheckIcon />
          </span>
          <p className={css.winTitle}>{data.alert.headline}</p>
          <p className={css.winSub}>{data.alert.headline_en}</p>
          <p className={css.winText} lang="te">
            {data.alert.text}
          </p>
          {data.alert.audio_url ? (
            <PlayButton
              state={player.state}
              active={player.isCurrent(data.alert.audio_url)}
              progress={player.progress}
              onClick={() => void player.toggle(data.alert!.audio_url)}
              label={player.state === "blocked" ? "Tap to play" : "Listen"}
            />
          ) : null}
          <p className={css.small}>{data.alert.audio_label}</p>
          <p className={css.winDue}>
            Baaki still due: <b>{data.balance_display}</b>
          </p>
        </section>
      ) : null}
    </div>
  );
}
