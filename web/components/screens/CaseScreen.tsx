"use client";

// Case (/case/[id]): balance, the case as a timeline (spoke → checked → letter → voice note → sent →
// reply / paid), the Polite → Firm → Formal ladder (make, letter preview, voice note, PDF, send),
// payment status and plan, employer replies, the legal-aid pack, and "Paisa aa gaya!" when a payment
// lands (the case is polled every ~3 s). A case that is still a draft shows the Confirm flow instead.

import { useState } from "react";
import Link from "next/link";
import { useAudioPlayer, useCase, useMessages, useT, type StepView } from "@/hooks";
import { copyText } from "@/lib/share";
import { inr, itemLabel, shortDate } from "@/lib/format";
import { mediaKeyUrl } from "@/lib/api";
import type { StringKey, UiLang } from "@/lib/i18n";
import type { CaseStatus, LadderStep } from "@/lib/types";
import { ArrowRightIcon, CheckIcon, FileIcon, PlayIcon, ShareIcon } from "@/components/ui/icons";
import {
  Confetti,
  ErrorNote,
  EstimateTag,
  GradientButton,
  Illustration,
  Loading,
  Money,
  MoneyFigure,
  PlayButton,
  Screen,
  StatusPill,
  avatarTone,
  type PillTone,
} from "@/components/ui/primitives";
import { ConfirmFlow } from "./ConfirmScreen";
import { VerifyBadge } from "@/components/features/verify/VerifyBadge";
import { ExitLink } from "@/components/features/exit/ExitLink";
import { InboxEntryButton } from "@/components/features/inbox/InboxEntryButton";
import { HisaabCaseCard } from "@/components/features/hisaab/HisaabWorker";

// Case-screen labels (kept local so the shared i18n table stays untouched).
type CaseLabels = {
  title: string;
  spoke: string;
  confirmed: string;
  letter: string;
  voice: string;
  sent: string;
  reply: string;
  claim: (employer: string, amount: string) => string;
  claimCta: string;
  copied: string;
  sentYes: string;
  replay: string;
  replayHint: string;
  notYetDue: string;
  plan: Record<string, string>;
};
const JOURNEY: Record<UiLang, CaseLabels> = {
  en: {
    title: "Your case",
    spoke: "You told Baaki",
    confirmed: "You checked it",
    letter: "Letter made",
    voice: "Voice note ready",
    sent: "Sent to employer",
    reply: "Reply or payment",
    claim: (e, a) => `${e} says ${a} was paid. Did it arrive?`,
    claimCta: "Check it",
    copied: "Copied. Did you send it on WhatsApp?",
    sentYes: "Yes, I sent it",
    replay: "Replay this case",
    replayHint: "Every step with its date, and the voice notes",
    notYetDue: "Not yet due",
    plan: { paid: "Paid", settled: "Paid", planned: "Planned", cancelled: "Not needed" },
  },
  "hi-en": {
    title: "Aapka case",
    spoke: "Aapne Baaki ko bataya",
    confirmed: "Aapne check kiya",
    letter: "Chitthi bani",
    voice: "Voice note taiyaar",
    sent: "Malik ko bheja",
    reply: "Jawab ya paisa",
    claim: (e, a) => `${e} कहते हैं ${a} दे दिए। पैसे मिले?`,
    claimCta: "देखिए",
    copied: "Copy हो गया। WhatsApp पर भेजा?",
    sentYes: "हाँ, भेज दिया",
    replay: "Case दोबारा देखिए",
    replayHint: "हर कदम, तारीख और voice notes के साथ",
    notYetDue: "अभी due नहीं",
    plan: { paid: "दे दिया", settled: "दे दिया", planned: "तय", cancelled: "ज़रूरत नहीं" },
  },
  te: {
    title: "మీ కేసు",
    spoke: "మీరు బాకీకి చెప్పారు",
    confirmed: "మీరు సరిచూశారు",
    letter: "ఉత్తరం తయారైంది",
    voice: "వాయిస్ నోట్ సిద్ధం",
    sent: "యజమానికి పంపారు",
    reply: "జవాబు లేదా డబ్బు",
    claim: (e, a) => `${a} ఇచ్చామని ${e} చెప్పారు. డబ్బులు అందాయా?`,
    claimCta: "చూడండి",
    copied: "కాపీ అయింది. WhatsAppలో పంపారా?",
    sentYes: "అవును, పంపాను",
    replay: "ఈ కేసును మళ్ళీ చూడండి",
    replayHint: "ప్రతి అడుగు, తేదీ, వాయిస్ నోట్లతో",
    notYetDue: "ఇంకా గడువు రాలేదు",
    plan: { paid: "చెల్లించారు", settled: "చెల్లించారు", planned: "ప్లాన్", cancelled: "అవసరం లేదు" },
  },
};

const STATUS_TONE: Partial<Record<CaseStatus, PillTone>> = {
  draft: "accent",
  confirmed: "neutral",
  sent: "accent",
  plan: "warn",
  paid: "success",
};

export function CaseScreen({ caseId }: { caseId: number }) {
  const { t, lang } = useT();
  const player = useAudioPlayer();
  const kase = useCase(caseId, {
    pollMs: 3000,
    onPaid: (c) => {
      if (c.audioUrl) void player.play(c.audioUrl);
    },
  });
  const msgs = useMessages(caseId, kase.caseData, { onChanged: kase.refresh });
  const [copied, setCopied] = useState(false);

  const c = kase.caseData;
  if (kase.loading && !c) {
    return (
      <Screen back="/app" t={t}>
        <Loading label={t("common.loading")} />
      </Screen>
    );
  }
  if (!c) {
    return (
      <Screen back="/app" t={t}>
        <ErrorNote message={kase.error} onRetry={kase.refresh} retryLabel={t("common.retry")} />
      </Screen>
    );
  }

  if (kase.isDraft) {
    return (
      <Screen title={c.employer?.name ?? t("case.title")} back="/app" t={t} className="case-screen">
        <StatusPill tone="accent" className="case-draft-pill">
          {t("case.not_confirmed")}
        </StatusPill>
        <ConfirmFlow resumeCaseId={c.id} onConfirmed={() => kase.refresh()} />
      </Screen>
    );
  }

  const employerUrl = msgs.employerUrl;
  const due = c.balance > 0;
  const name = c.employer?.name ?? t("case.title");
  const status: CaseStatus = kase.isPaid ? "paid" : c.status;
  const statusTone = STATUS_TONE[status];
  const paidShare = c.total_due > 0 ? Math.min(1, Math.max(0, c.amount_paid / c.total_due)) : 0;

  // The case as a timeline: what has happened so far, and what is next.
  const J = JOURNEY[lang];
  const views = msgs.steps.map((s) => msgs.views[s]).filter((v): v is StepView => !!v);
  const sentView = views.find((v) => msgs.isSent(v)) ?? null;
  const journey = [
    { k: "spoke", label: J.spoke, done: true, when: shortDate(c.created_at, lang) },
    { k: "confirmed", label: J.confirmed, done: true, when: shortDate(c.confirmed_at, lang) },
    { k: "letter", label: J.letter, done: views.length > 0, when: views[0] ? shortDate(views[0].createdAt, lang) : "" },
    { k: "voice", label: J.voice, done: views.some((v) => !!v.audioUrl), when: "" },
    { k: "sent", label: J.sent, done: !!sentView, when: sentView ? shortDate(sentView.sentAt, lang) : "" },
    { k: "reply", label: kase.isPaid ? t("state.paid") : J.reply, done: kase.isPaid || kase.replies.length > 0, when: "" },
  ];
  const nextIdx = journey.findIndex((j) => !j.done);

  return (
    <Screen title={name} back="/app" t={t} className="case-screen">
      <section className="case-hero total-box" data-paid={kase.isPaid} aria-label={t("case.balance")}>
        <div className="case-hero-top">
          <span className="case-avatar" data-tone={avatarTone(name)} aria-hidden="true">
            {name.slice(0, 1).toUpperCase()}
          </span>
          <div className="case-hero-who">
            <p className="case-hero-name">{name}</p>
            {c.employer?.locality ? <p className="meta">{c.employer.locality}</p> : null}
          </div>
          {statusTone ? <StatusPill tone={statusTone}>{t(`state.${status}` as StringKey)}</StatusPill> : null}
        </div>
        <div className="case-hero-amount">
          <p className="total-label">{t("case.balance")}</p>
          <p className="total-value">
            <MoneyFigure value={c.balance} size="xl" />
          </p>
        </div>
        {c.amount_paid > 0 ? (
          <div className="case-progress">
            <span className="case-progress-track" aria-hidden="true">
              <span className="case-progress-fill" style={{ width: `${Math.round(paidShare * 100)}%` }} />
            </span>
            <p className="meta">
              {t("case.paid")}: <Money value={c.amount_paid} />
            </p>
          </div>
        ) : null}
        {c.employer?.fair_employer ? <span className="badge badge-fair">{t("home.fair")}</span> : null}
      </section>

      {/* The employer tapped "I've paid": a claim until she says the money arrived (Hisaab flow). */}
      {(c.pending_claims?.count ?? 0) > 0 ? (
        <Link href={`/hisaab/${c.id}`} className="claim-card" aria-live="polite">
          <span className="claim-card-icon" aria-hidden="true">
            <span className="claim-card-dot" />
          </span>
          <span className="claim-card-text">{J.claim(name, inr(c.pending_claims?.amount ?? 0))}</span>
          <span className="claim-card-cta">
            {J.claimCta} <ArrowRightIcon />
          </span>
        </Link>
      ) : null}

      <section className="card journey" aria-label={J.title}>
        <div className="journey-head">
          <h2 className="card-title">{J.title}</h2>
          <span className="journey-count">
            {journey.filter((j) => j.done).length}/{journey.length}
          </span>
        </div>
        <ol className="journey-list">
          {journey.map((j, i) => (
            <li key={j.k} className="journey-step" data-done={j.done} aria-current={i === nextIdx ? "step" : undefined}>
              <span className="journey-node" aria-hidden="true">
                {j.done ? <CheckIcon /> : null}
              </span>
              <span className="journey-label">{j.label}</span>
              {j.when ? <span className="journey-when">{j.when}</span> : null}
            </li>
          ))}
        </ol>
      </section>

      {!due && !kase.isPaid ? <p className="muted">{t("case.nothing_due")}</p> : null}

      {due ? (
        <section aria-label={t("case.ladder")}>
          <h2 className="section-title">{t("case.ladder")}</h2>
          <ol className="ladder">
            {msgs.steps.map((step, i) => (
              <StepCard
                key={step}
                index={i}
                step={step}
                view={msgs.views[step]}
                state={msgs.state[step]}
                recommended={msgs.nextStep === step}
                sent={msgs.isSent(msgs.views[step])}
                t={t}
                lang={lang}
                player={player}
                onMake={(regenerate) => void msgs.generate(step, { regenerate })}
                onShare={() => void msgs.share(step)}
                onConfirmSent={() => void msgs.confirmSent(step)}
                labels={J}
              />
            ))}
          </ol>
        </section>
      ) : null}

      <InboxEntryButton caseId={c.id} />

      {/* Hisaab proposals (renders nothing until one exists); a pending payment claim has its own card above */}
      {(c.pending_claims?.count ?? 0) > 0 ? null : <HisaabCaseCard caseId={c.id} />}

      {kase.plan.length ? (
        <section className="card case-plan" aria-label={t("case.plan")}>
          <h2 className="card-title">{t("case.plan")}</h2>
          <ol className="plan-list">
            {kase.plan.map((p) => (
              <li key={p.id} className="plan-row" data-status={p.status}>
                <span className="plan-no" aria-hidden="true">
                  {p.status === "paid" ? <CheckIcon /> : p.instalment_no}
                </span>
                <span className="plan-text">
                  <span className="plan-amount">
                    {t("case.instalment")} {p.instalment_no}/{p.instalments_total}: <Money value={p.amount} />
                  </span>
                  <span className="meta">{shortDate(p.due_date, lang)}</span>
                </span>
                <StatusPill tone={p.status === "paid" || p.status === "settled" ? "success" : "neutral"}>{J.plan[p.status] ?? p.status}</StatusPill>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {kase.replies.length ? (
        <section className="card case-replies" aria-label={t("case.replies")}>
          <h2 className="card-title">{t("case.replies")}</h2>
          <ul className="plain-list">
            {kase.replies.map((r) => {
              const url = mediaKeyUrl(r.audio_path);
              return (
                <li key={r.id} className="reply reply-bubble">
                  <p>{r.text}</p>
                  {url ? (
                    <PlayButton
                      state={player.state}
                      active={player.isCurrent(url)}
                      progress={player.progress}
                      onClick={() => void player.toggle(url)}
                      label={t("common.listen")}
                    />
                  ) : null}
                  <p className="meta">{shortDate(r.sent_at ?? r.created_at, lang)}</p>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <details className="card receipt-details">
        <summary className="card-title">
          <span>{t("case.items")}</span>
          <span className="money">{inr(c.total_due)}</span>
        </summary>
        <ul className="items">
          {c.items.map((it) => (
            <li key={it.id} className="item" data-kind={it.kind} data-included={it.included_in_total}>
              <div className="item-row">
                <span className="item-label" title={it.label}>
                  {itemLabel(t, it, lang)} {it.is_estimate ? <EstimateTag t={t} /> : null}
                  {it.kind === "not_yet_due" ? <span className="tag">{J.notYetDue}</span> : null}
                </span>
                <Money value={it.amount} />
              </div>
              <p className="meta">{it.source}</p>
            </li>
          ))}
        </ul>
      </details>

      {employerUrl ? (
        <section className="case-links">
          <a href={c.employer_path} className="btn" target="_blank" rel="noreferrer">
            {t("case.employer_link")}
          </a>
          <button
            type="button"
            className="btn"
            onClick={async () => {
              setCopied(await copyText(employerUrl));
            }}
          >
            {copied ? t("common.copied") : t("common.copy")}
          </button>
        </section>
      ) : null}

      {kase.legalPackUrl ? (
        <a href={kase.legalPackUrl} className="card legal-pack" target="_blank" rel="noreferrer">
          <span className="legal-pack-icon" aria-hidden="true">
            <FileIcon />
          </span>
          <span className="legal-pack-text">
            <strong>{t("case.legal_pack")}</strong>
            <span className="hint">{t("case.legal_pack_hint")}</span>
          </span>
          <ArrowRightIcon className="legal-pack-arrow" />
        </a>
      ) : null}

      <Link href={`/story/${c.id}`} className="card legal-pack case-replay">
        <span className="legal-pack-icon" aria-hidden="true">
          <PlayIcon />
        </span>
        <span className="legal-pack-text">
          <strong>{J.replay}</strong>
          <span className="hint">{J.replayHint}</span>
        </span>
        <ArrowRightIcon className="legal-pack-arrow" />
      </Link>

      <ExitLink employerId={c.employer?.id} caseId={c.id} />

      <p className="footnote">{t("common.not_legal_advice")}</p>

      {kase.celebration ? (
        <div className="celebrate" role="dialog" aria-modal="true" aria-labelledby="paisa-title">
          <span className="celebrate-rays" aria-hidden="true" />
          <Confetti />
          <div className="celebrate-card">
            <span className="celebrate-art" data-bleed="bottom">
              <Illustration name="celebrate" />
            </span>
            <p id="paisa-title" className="celebrate-title">
              {t("paisa.title")}
            </p>
            <p className="celebrate-amount">{inr(kase.celebration.amountPaid)}</p>
            {kase.celebration.text ? <p className="celebrate-text">{kase.celebration.text}</p> : null}
            {kase.celebration.audioUrl ? (
              <PlayButton
                state={player.state}
                active={player.isCurrent(kase.celebration.audioUrl)}
                progress={player.progress}
                onClick={() => void player.toggle(kase.celebration!.audioUrl)}
                label={player.state === "blocked" ? t("common.tap_to_play") : t("common.listen")}
              />
            ) : null}
            <GradientButton onClick={kase.dismissCelebration}>{t("paisa.ok")}</GradientButton>
          </div>
        </div>
      ) : null}
    </Screen>
  );
}

function StepCard({
  index,
  step,
  view,
  state,
  recommended,
  sent,
  t,
  lang,
  player,
  onMake,
  onShare,
  onConfirmSent,
  labels,
}: {
  index: number;
  step: LadderStep;
  view: StepView | null;
  state: { generating: boolean; error: string | null; sharing: boolean; shareResult: string | null; awaitingSentConfirm?: boolean };
  recommended: boolean;
  sent: boolean;
  t: ReturnType<typeof useT>["t"];
  lang: string;
  player: ReturnType<typeof useAudioPlayer>;
  onMake: (regenerate: boolean) => void;
  onShare: () => void;
  onConfirmSent: () => void;
  labels: CaseLabels;
}) {
  const status = sent ? "sent" : view ? "ready" : recommended ? "next" : "later";
  return (
    <li className="step" data-step={step} data-status={status} aria-current={recommended ? "step" : undefined}>
      <span className="step-node" aria-hidden="true">
        {sent ? <CheckIcon /> : index + 1}
      </span>
      <div className="step-card card">
        <div className="step-head">
          <h3 className="step-title">{t(`case.step.${step}` as StringKey)}</h3>
          {sent ? (
            <StatusPill tone="success">
              {t("case.shared")} · {shortDate(view?.sentAt, lang)}
            </StatusPill>
          ) : view ? (
            <StatusPill tone="accent">{t("state.confirmed")}</StatusPill>
          ) : null}
        </div>
        <p className="hint">{t(`case.step.${step}_hint` as StringKey)}</p>

        {state.generating ? <Loading label={t("case.making")} /> : null}
        <ErrorNote message={state.error} />

        {view && !state.generating ? (
          <div className="stack step-content">
            <div className="message-text letter-preview">
              <p className="field-label">{t("case.employer_text")}</p>
              <p lang={view.language}>{view.text}</p>
            </div>
            {view.textWorkerLang ? (
              <details className="message-text worker-lang">
                <summary>{t("case.your_text")}</summary>
                <p>{view.textWorkerLang}</p>
              </details>
            ) : null}
            <div className="step-media">
              {view.audioUrl ? (
                <PlayButton
                  state={player.state}
                  active={player.isCurrent(view.audioUrl)}
                  progress={player.progress}
                  onClick={() => void player.toggle(view.audioUrl)}
                  label={view.voiceMode === "clone" ? t("case.voice_mode_clone") : t("common.listen")}
                />
              ) : (
                <p className="hint">{t("common.audio_failed")}</p>
              )}
              {view.pdfUrl ? (
                <a href={view.pdfUrl} className="btn" target="_blank" rel="noreferrer">
                  <FileIcon /> {t("case.pdf")}
                </a>
              ) : null}
            </div>
            {view.audioUrl ? <VerifyBadge messageId={view.messageId} workerLang={lang} /> : null}
            {sent ? (
              <button type="button" className="btn btn-big" onClick={onShare} disabled={state.sharing}>
                <ShareIcon /> {t("case.share")}
              </button>
            ) : (
              <GradientButton onClick={onShare} disabled={state.sharing} icon={<ShareIcon />}>
                {t("case.share")}
              </GradientButton>
            )}
            {state.awaitingSentConfirm ? (
              <div className="sent-confirm" role="status">
                <p>{labels.copied}</p>
                <button type="button" className="btn btn-small" onClick={onConfirmSent}>
                  <CheckIcon /> {labels.sentYes}
                </button>
              </div>
            ) : state.shareResult === "copied" ? (
              <p className="meta">{t("common.copied")}</p>
            ) : null}
            <button type="button" className="btn btn-small btn-ghost step-remake" onClick={() => onMake(true)}>
              {t("case.remake")}
            </button>
          </div>
        ) : null}

        {!view && !state.generating ? (
          <button type="button" className={`btn btn-big step-make ${recommended ? "btn-primary" : ""}`} onClick={() => onMake(false)}>
            {t("case.make")}
          </button>
        ) : null}
      </div>
    </li>
  );
}
