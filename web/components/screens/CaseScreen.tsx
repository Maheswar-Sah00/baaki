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
import type { LadderStep } from "@/lib/types";
import { FileIcon, ShareIcon } from "@/components/ui/icons";
import { Confetti, ErrorNote, EstimateTag, Illustration, Loading, Money, PlayButton, Screen } from "@/components/ui/primitives";
import { ConfirmFlow } from "./ConfirmScreen";
import { VerifyBadge } from "@/components/features/verify/VerifyBadge";
import { ExitLink } from "@/components/features/exit/ExitLink";
import { InboxEntryButton } from "@/components/features/inbox/InboxEntryButton";

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
        <p className="tag" data-state="draft">
          {t("case.not_confirmed")}
        </p>
        <ConfirmFlow resumeCaseId={c.id} onConfirmed={() => kase.refresh()} />
      </Screen>
    );
  }

  const employerUrl = msgs.employerUrl;
  const due = c.balance > 0;

  return (
    <Screen title={c.employer?.name ?? t("case.title")} back="/app" t={t} className="case-screen">
      <section className="total-box" data-paid={kase.isPaid}>
        <p className="total-label">{t("case.balance")}</p>
        <p className="total-value">{inr(c.balance)}</p>
        {c.amount_paid > 0 ? (
          <p className="meta">
            {t("case.paid")}: <Money value={c.amount_paid} />
          </p>
        ) : null}
        {c.employer?.fair_employer ? <span className="badge badge-fair">{t("home.fair")}</span> : null}
        {kase.isPaid ? <p className="tag" data-state="paid">{t("state.paid")}</p> : null}
      </section>

      {!due && !kase.isPaid ? <p className="muted">{t("case.nothing_due")}</p> : null}

      {due ? (
        <section aria-label={t("case.ladder")}>
          <h2 className="section-title">{t("case.ladder")}</h2>
          <ol className="ladder">
            {msgs.steps.map((step) => (
              <StepCard
                key={step}
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

      {kase.plan.length ? (
        <section className="card" aria-label={t("case.plan")}>
          <h2 className="card-title">{t("case.plan")}</h2>
          <ol className="plain-list">
            {kase.plan.map((p) => (
              <li key={p.id} data-status={p.status}>
                {t("case.instalment")} {p.instalment_no}/{p.instalments_total}: <Money value={p.amount} /> · {shortDate(p.due_date, lang)} ·{" "}
                {p.status}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <InboxEntryButton caseId={c.id} />

      {kase.replies.length ? (
        <section className="card" aria-label={t("case.replies")}>
          <h2 className="card-title">{t("case.replies")}</h2>
          <ul className="plain-list">
            {kase.replies.map((r) => {
              const url = mediaKeyUrl(r.audio_path);
              return (
                <li key={r.id} className="reply">
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

      <details className="card">
        <summary className="card-title">{t("case.items")}</summary>
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
        <section className="row">
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
          <FileIcon />
          <span>
            <strong>{t("case.legal_pack")}</strong>
            <span className="hint">{t("case.legal_pack_hint")}</span>
          </span>
        </a>
      ) : null}

      <ExitLink employerId={c.employer?.id} caseId={c.id} />

      <p className="footnote">{t("common.not_legal_advice")}</p>

      {kase.celebration ? (
        <div className="celebrate" role="dialog" aria-modal="true" aria-labelledby="paisa-title">
          <Confetti />
          <div className="celebrate-card">
            <Illustration name="celebrate" animated />
            <p id="paisa-title" className="celebrate-title">
              {t("paisa.title")}
            </p>
            <p className="celebrate-amount">{inr(kase.celebration.amountPaid)}</p>
            {kase.celebration.text ? <p>{kase.celebration.text}</p> : null}
            {kase.celebration.audioUrl ? (
              <PlayButton
                state={player.state}
                active={player.isCurrent(kase.celebration.audioUrl)}
                progress={player.progress}
                onClick={() => void player.toggle(kase.celebration!.audioUrl)}
                label={player.state === "blocked" ? t("common.tap_to_play") : t("common.listen")}
              />
            ) : null}
            <button type="button" className="btn btn-primary btn-big" onClick={kase.dismissCelebration}>
              {t("paisa.ok")}
            </button>
          </div>
        </div>
      ) : null}
    </Screen>
  );
}

function StepCard({
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
    <li className="step card" data-step={step} data-status={status}>
      <div className="step-head">
        <h3 className="step-title">{t(`case.step.${step}` as StringKey)}</h3>
        {sent ? (
          <span className="tag" data-state="sent">
            {t("case.shared")} · {shortDate(view?.sentAt, lang)}
          </span>
        ) : null}
      </div>
      <p className="hint">{t(`case.step.${step}_hint` as StringKey)}</p>

      {state.generating ? <Loading label={t("case.making")} /> : null}
      <ErrorNote message={state.error} />

      {view && !state.generating ? (
        <div className="stack">
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
          <div className="row">
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
          <button type="button" className="btn btn-primary btn-big" onClick={onShare} disabled={state.sharing}>
            <ShareIcon /> {t("case.share")}
          </button>
          {state.shareResult === "copied" ? <p className="meta">{t("common.copied")}</p> : null}
          <button type="button" className="btn btn-small" onClick={() => onMake(true)}>
            {t("case.remake")}
          </button>
        </div>
      ) : null}

      {!view && !state.generating ? (
        <button type="button" className={`btn btn-big ${recommended ? "btn-primary" : ""}`} onClick={() => onMake(false)}>
          {t("case.make")}
        </button>
      ) : null}
    </li>
  );
}
