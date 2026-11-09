"use client";

// Case (/case/[id]): balance, the Polite → Firm → Formal ladder (make, listen, PDF, share), payment
// status and plan, employer replies, the legal-aid pack, and "Paisa aa gaya!" when a payment lands
// (the case is polled every ~3 s). A case that is still a draft shows the Confirm flow instead.

import { useState } from "react";
import { useAudioPlayer, useCase, useMessages, useT, type StepView } from "@/hooks";
import { copyText } from "@/lib/share";
import { inr, itemLabel, shortDate } from "@/lib/format";
import { mediaKeyUrl } from "@/lib/api";
import type { StringKey } from "@/lib/i18n";
import type { CaseStatus, LadderStep } from "@/lib/types";
import { ArrowRightIcon, CheckIcon, FileIcon, ShareIcon } from "@/components/ui/icons";
import {
  Confetti,
  ErrorNote,
  EstimateTag,
  GradientButton,
  Illustration,
  Loading,
  Money,
  PlayButton,
  Screen,
  StatusPill,
  type PillTone,
} from "@/components/ui/primitives";
import { ConfirmFlow } from "./ConfirmScreen";
import { VerifyBadge } from "@/components/features/verify/VerifyBadge";
import { ExitLink } from "@/components/features/exit/ExitLink";
import { InboxEntryButton } from "@/components/features/inbox/InboxEntryButton";

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

  return (
    <Screen title={name} back="/app" t={t} className="case-screen">
      <section className="case-hero total-box" data-paid={kase.isPaid} aria-label={t("case.balance")}>
        <span className="haze" aria-hidden="true" />
        <div className="case-hero-top">
          <span className="case-avatar" aria-hidden="true">
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
          <p className="total-value">{inr(c.balance)}</p>
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
              />
            ))}
          </ol>
        </section>
      ) : null}

      <InboxEntryButton caseId={c.id} />

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
                <StatusPill tone={p.status === "paid" ? "success" : "neutral"}>{p.status}</StatusPill>
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

      <ExitLink employerId={c.employer?.id} caseId={c.id} />

      <p className="footnote">{t("common.not_legal_advice")}</p>

      {kase.celebration ? (
        <div className="celebrate" role="dialog" aria-modal="true" aria-labelledby="paisa-title">
          <span className="celebrate-rays" aria-hidden="true" />
          <Confetti />
          <div className="celebrate-card">
            <Illustration name="celebrate" animated />
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
}: {
  index: number;
  step: LadderStep;
  view: StepView | null;
  state: { generating: boolean; error: string | null; sharing: boolean; shareResult: string | null };
  recommended: boolean;
  sent: boolean;
  t: ReturnType<typeof useT>["t"];
  lang: string;
  player: ReturnType<typeof useAudioPlayer>;
  onMake: (regenerate: boolean) => void;
  onShare: () => void;
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
            <div className="message-text">
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
            {state.shareResult === "copied" ? <p className="meta">{t("common.copied")}</p> : null}
            <button type="button" className="btn btn-small btn-ghost step-remake" onClick={() => onMake(true)}>
              {t("case.remake")}
            </button>
          </div>
        ) : null}

        {!view && !state.generating ? (
          <button type="button" className={`btn btn-big ${recommended ? "btn-primary" : ""}`} onClick={() => onMake(false)}>
            {t("case.make")}
          </button>
        ) : null}
      </div>
    </li>
  );
}
