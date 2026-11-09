"use client";

// /raise/e/[token]: Haq Raise, the employer side, in the EMPLOYER's language. Play her note, see the request and a
// small "why" (the cost per working day; the legal estimate only if she chose to mention it). Accept, step it up,
// or "Let's talk" (a voice reply she hears in her language). On accept: agreement PDF + payday reminder.

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  BottomSheet,
  Card,
  ErrorNote,
  GradientButton,
  Illustration,
  Loading,
  MicButton,
  PlayButton,
  Screen,
  SkeletonCard,
  StatusPill,
} from "@/components/ui/primitives";
import { BellIcon, CheckIcon, FileIcon } from "@/components/ui/icons";
import { useAudioPlayer, usePressToTalk, useRecorder } from "@/hooks";
import {
  HTML_LANG,
  media,
  raiseApi,
  raiseError,
  rupees,
  type EmployerRaiseView,
} from "@/lib/features/raise";
import { employerStrings } from "./strings";
import css from "./raise.module.css";

export function RaiseEmployerScreen({ token }: { token: string }) {
  const [v, setV] = useState<EmployerRaiseView | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "asked" | "step" | "talk">(null);
  const [talkOpen, setTalkOpen] = useState(false);
  const [talkText, setTalkText] = useState("");
  const [talkDone, setTalkDone] = useState(false);
  const playedRef = useRef(false);
  const player = useAudioPlayer();

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setV(await raiseApi.employer(token, signal));
        setError(null);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        if ((e as { status?: number }).status === 404) setNotFound(true);
        else setError(raiseError(e));
      } finally {
        setLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    const ac = new AbortController();
    // load() sets state only after its fetch resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(ac.signal);
    return () => ac.abort();
  }, [load]);

  const lang = v?.employer.language ?? "en";
  const S = employerStrings(lang);
  const worker = v?.worker.name_display ?? "";

  const playNote = () => {
    const url = media(v?.audio_url);
    if (!url) return;
    void player.toggle(url);
    if (!playedRef.current) {
      playedRef.current = true;
      raiseApi.played(token).catch(() => undefined);
    }
  };

  const answer = async (choice: "asked" | "step") => {
    setBusy(choice);
    setError(null);
    try {
      await raiseApi.accept(token, choice);
      await load();
    } catch (e) {
      setError(raiseError(e));
    } finally {
      setBusy(null);
    }
  };

  const sendTalk = useCallback(
    async (input: { audio?: Blob; filename?: string; text?: string }) => {
      setBusy("talk");
      setError(null);
      try {
        await raiseApi.talk(token, { ...input, lang });
        setTalkDone(true);
        setTalkText("");
        setTalkOpen(false);
        await load();
      } catch (e) {
        setError(raiseError(e));
      } finally {
        setBusy(null);
      }
    },
    [token, lang, load],
  );

  const rec = useRecorder({ onRecorded: (r) => void sendTalk({ audio: r.blob, filename: r.filename }), maxMs: 30_000 });
  const ptt = usePressToTalk(rec, { disabled: busy !== null });

  if (loading && !v) {
    return (
      <Screen safetyLink={false}>
        <div role="status" aria-label="Loading" className="stack">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </Screen>
    );
  }
  if (notFound || !v) {
    return (
      <Screen safetyLink={false}>
        <Card tone="soft">
          <p style={{ margin: 0 }}>{notFound ? S.notFound : error}</p>
        </Card>
      </Screen>
    );
  }

  const audio = media(v.audio_url);
  const step = v.plan === "step" && v.step1_amount;
  const done = v.answer;

  return (
    <Screen title={S.title(worker)} safetyLink={false}>
      <div lang={HTML_LANG[lang]} className="stack">
        <Card tone="glow" className={`${css.message} ${css.rise}`}>
          {audio ? (
            <PlayButton
              state={player.state}
              active={player.isCurrent(audio)}
              progress={player.progress}
              onClick={playNote}
              label={player.state === "blocked" ? S.tapToPlay : S.listen(worker)}
            />
          ) : null}
          {v.message.disclosure ? <p className={css.disclosure}>{v.message.disclosure}</p> : null}
          <p className={css.messageText}>{v.message.sentences.join(" ")}</p>
        </Card>

        <Card className={css.rise}>
          <p className={css.eyebrow}>{S.request}</p>
          <div className={css.ask}>
            <div>
              <p className={css.small}>{S.now}</p>
              <p className={css.askValue}>{rupees(v.current)}</p>
            </div>
            <span className={css.arrow} aria-hidden="true">
              →
            </span>
            <div>
              <p className={css.small}>{step ? S.from(v.start_display ?? "") : S.from(v.start_display ?? "")}</p>
              <p className={`${css.askValue} ${css.askGrad}`}>{rupees(step ? v.step1_amount : v.ask_amount)}</p>
            </div>
          </div>
          {step ? <p className={css.small}>{S.then(rupees(v.ask_amount), v.step_display ?? "")}</p> : null}
        </Card>

        <Card tone="soft" className={`${css.why} ${css.rise}`}>
          <p className={css.eyebrow}>{S.why}</p>
          <p className={css.perDay}>{step && v.why.per_day_step1_text ? v.why.per_day_step1_text : v.why.per_day_text}</p>
          {v.why.legal_text ? (
            <p className={css.small}>
              {v.why.legal_text} <StatusPill tone="estimate">{S.estimate}</StatusPill>
            </p>
          ) : v.why.fair_pay_link ? (
            <Link href={v.why.fair_pay_link} className="meta" style={{ color: "var(--accent-text)", fontWeight: 600 }}>
              {v.why.fair_pay_text} →
            </Link>
          ) : null}
        </Card>

        <ErrorNote message={error} />

        {done ? (
          <Card tone="success" className={`${css.won} ${css.rise}`}>
            <Illustration name="handshake" size={140} />
            <p className="display" style={{ margin: 0, fontSize: "2rem" }}>
              {S.doneTitle}
            </p>
            <p style={{ margin: 0 }}>{S.doneText(worker, rupees(done.new_wage), v.start_display ?? "")}</p>
            {done.step_up_to ? (
              <p className={css.small}>{S.then(rupees(done.step_up_to), v.step_display ?? v.step_offer?.step_display ?? "")}</p>
            ) : null}
            <div className={css.links}>
              {v.agreement_url ? (
                <a className="btn" href={media(v.agreement_url) ?? "#"} target="_blank" rel="noopener noreferrer">
                  <FileIcon /> {S.agreement}
                </a>
              ) : null}
              {v.ics_url ? (
                <a className="btn" href={v.ics_url} download>
                  <BellIcon /> {S.ics}
                </a>
              ) : null}
            </div>
          </Card>
        ) : v.can_answer ? (
          <div className={css.answerBtns}>
            {busy === "asked" || busy === "step" ? <Loading label="…" /> : null}
            <GradientButton onClick={() => void answer("asked")} disabled={busy !== null} icon={<CheckIcon />}>
              {S.accept} ·{" "}
              {step
                ? S.stepSub(rupees(v.step1_amount), v.start_display ?? "", rupees(v.ask_amount), v.step_display ?? "")
                : S.acceptSub(rupees(v.ask_amount), v.start_display ?? "")}
            </GradientButton>
            {v.step_offer ? (
              <button type="button" className={css.answerBtn} onClick={() => void answer("step")} disabled={busy !== null}>
                <span>{S.stepUp}</span>
                <span className={css.answerSub}>
                  {S.stepSub(
                    rupees(v.step_offer.step1),
                    v.step_offer.start_display ?? "",
                    rupees(v.ask_amount),
                    v.step_offer.step_display ?? "",
                  )}
                </span>
              </button>
            ) : null}
            <button type="button" className={css.answerBtn} onClick={() => setTalkOpen(true)} disabled={busy !== null}>
              <span>{S.talk}</span>
              <span className={css.answerSub}>{S.talkHint(worker)}</span>
            </button>
          </div>
        ) : null}

        {talkDone ? <p className={css.hint}>{S.replySent(worker)}</p> : null}

        {v.replies.length ? (
          <section className={css.section}>
            <h2 className="section-title">{S.yourReplies}</h2>
            <ul className={css.timeline}>
              {v.replies.map((e) => (
                <li key={e.id} className={css.timelineItem}>
                  <span className={css.dot} aria-hidden="true" />
                  <div className={css.reply}>
                    <p>{e.text}</p>
                    {e.original_audio_url ? (
                      <PlayButton
                        state={player.state}
                        active={player.isCurrent(media(e.original_audio_url))}
                        progress={player.progress}
                        onClick={() => void player.toggle(media(e.original_audio_url))}
                        label={S.tapToPlay}
                      />
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <p className="footnote">{v.ai_notice}</p>
      </div>

      <BottomSheet open={talkOpen} onClose={() => setTalkOpen(false)} title={S.talk}>
        <div className={css.talk} lang={HTML_LANG[lang]}>
          <p className={css.hint}>{S.talkHint(worker)}</p>
          <MicButton
            state={busy === "talk" ? "starting" : rec.state}
            level={rec.level}
            elapsedMs={rec.elapsedMs}
            disabled={busy !== null}
            handlers={ptt}
            label={busy === "talk" ? S.sending : S.record}
          />
          {rec.error ? <p className={css.hint}>{rec.error}</p> : null}
          <form
            className={css.field}
            style={{ width: "100%" }}
            onSubmit={(e) => {
              e.preventDefault();
              if (talkText.trim()) void sendTalk({ text: talkText.trim() });
            }}
          >
            <span className="field-label">{S.typeInstead}</span>
            <textarea
              className={`${css.input} ${css.textarea}`}
              value={talkText}
              placeholder={S.typePlaceholder}
              onChange={(e) => setTalkText(e.target.value)}
              maxLength={600}
            />
            <button type="submit" className="btn" disabled={busy !== null || !talkText.trim()}>
              {busy === "talk" ? S.sending : S.sendReply}
            </button>
          </form>
        </div>
      </BottomSheet>
    </Screen>
  );
}
