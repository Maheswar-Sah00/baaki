"use client";

// Employer page (/e/[token]): public, no login, in the employer's language. It reads like a calm, respectful
// statement: who it is from, what is owed, every line with the law it comes from, the voice note with its AI
// disclosure, then the actions: pay by UPI (deep link on phones, QR + UPI ID on desktops), "I've paid", pay in
// 2 or 3 parts, or reply by voice. Fair Employer badge after full payment.

import { useEmployerPage, usePressToTalk, useStrings } from "@/hooks";
import { inr, shortDate } from "@/lib/format";
import { uiLangOf, type UiLang } from "@/lib/i18n";
import { shareMessage } from "@/lib/share";
import { BotIcon, CheckIcon, FileIcon, ShareIcon } from "@/components/ui/icons";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { SomethingDifferentLink } from "@/components/features/hisaab/HisaabEmployer";
import { Confetti, ErrorNote, EstimateTag, Loading, MicButton, Money, PlayButton, Screen, avatarTone } from "@/components/ui/primitives";

// Page-only copy in the employer's language (the rest comes from the shared i18n keys).
const EX: Record<
  UiLang,
  {
    stmt: (employer: string) => string;
    how: string;
    sent: string;
    voice: (worker: string) => string;
    wait: (worker: string) => string;
    claims: string;
    typed: string;
    typedPh: (worker: string) => string;
    send: string;
    overpaid: (amount: string) => string;
  }
> = {
  en: {
    stmt: (e) => `Statement for ${e}`,
    how: "Every line shows the rule it comes from. Tap § to read it.",
    sent: "Sent with Baaki",
    voice: (w) => `A voice note from ${w}`,
    wait: (w) => `Waiting for ${w} to confirm`,
    claims: "Your payments",
    typed: "Or type a reply",
    typedPh: (w) => `Write to ${w}…`,
    send: "Send",
    overpaid: (a) => `You have paid ${a} more than the total.`,
  },
  te: {
    stmt: (e) => `${e} గారికి లెక్క`,
    how: "ప్రతి లైన్ ఏ నియమం నుండి వచ్చిందో చూపిస్తుంది. చదవడానికి § నొక్కండి.",
    sent: "బాకీ ద్వారా పంపబడింది",
    voice: (w) => `${w} నుండి వాయిస్ నోట్`,
    wait: (w) => `${w} నిర్ధారణ కోసం ఎదురుచూస్తున్నాం`,
    claims: "మీ చెల్లింపులు",
    typed: "లేదా జవాబు టైప్ చేయండి",
    typedPh: (w) => `${w}కి రాయండి…`,
    send: "పంపండి",
    overpaid: (a) => `మొత్తం కంటే ${a} ఎక్కువ చెల్లించారు.`,
  },
  "hi-en": {
    stmt: (e) => `${e} के लिए हिसाब`,
    how: "हर line के साथ उसका नियम लिखा है। पढ़ने के लिए § दबाएँ।",
    sent: "Baaki से भेजा गया",
    voice: (w) => `${w} का voice note`,
    wait: (w) => `${w} की पुष्टि का इंतज़ार`,
    claims: "आपके payments",
    typed: "या जवाब लिखें",
    typedPh: (w) => `${w} को लिखें…`,
    send: "भेजें",
    overpaid: (a) => `आपने कुल से ${a} ज़्यादा दिया है।`,
  },
};

export function EmployerScreen({ token }: { token: string }) {
  const emp = useEmployerPage(token);
  const ui = uiLangOf(emp.page?.employer.language);
  const t = useStrings(ui);
  const L = EX[ui] ?? EX.en;
  const press = usePressToTalk(emp.reply.recorder, { disabled: emp.reply.sending });

  if (emp.loading) {
    return (
      <Screen safetyLink={false} className="fx employer-fx">
        <Loading label={t("common.loading")} />
      </Screen>
    );
  }
  if (!emp.page) {
    return (
      <Screen safetyLink={false} className="fx employer-fx">
        <ErrorNote message={emp.notFound ? t("emp.not_found") : emp.error} onRetry={emp.notFound ? undefined : emp.refresh} retryLabel={t("common.retry")} />
      </Screen>
    );
  }

  const p = emp.page;
  const due = p.balance > 0.5;
  const upi = emp.upi;
  const initial = p.worker.name.slice(0, 1).toUpperCase();

  return (
    <Screen title={t("emp.title", { name: p.worker.name })} safetyLink={false} className="employer-screen fx employer-fx">
      <div lang={p.employer.language === "te-IN" ? "te" : p.employer.language === "hi-en" ? "hi" : "en"} className="emp-layout">
        <div className="emp-main">
          {emp.badge ? (
            <section className="fx-panel ex-badge" data-wash="sage" aria-label={t("emp.fair")}>
              <Confetti pieces={18} />
              <span className="vx-check" aria-hidden="true" style={{ width: 52, height: 52 }}>
                <CheckIcon />
              </span>
              <p className="fx-h">{t("emp.fair")}</p>
              <p className="fx-sub fx-wash-ink">{emp.badge.text}</p>
              <button type="button" className="fx-pill-btn" data-ink onClick={() => void shareMessage({ text: emp.badge!.share_text, title: "Fair Employer" })}>
                <ShareIcon /> {t("emp.share_badge")}
              </button>
            </section>
          ) : null}

          {emp.audioUrl ? (
            <section className="fx-panel ex-voice voice-note" data-wash="lilac">
              {emp.stale && emp.staleNote ? <p className="ex-stale">{emp.staleNote}</p> : null}
              <p className="ex-voice-title">{L.voice(p.worker.name)}</p>
              <PlayButton
                state={emp.player.state}
                active={emp.player.isCurrent(emp.audioUrl)}
                progress={emp.player.progress}
                onClick={() => void emp.play()}
                label={t("emp.play")}
              />
              <p className="ex-ai">
                <BotIcon /> {t("emp.ai_notice")}
              </p>
            </section>
          ) : null}

          {/* the statement */}
          <section className="fx-panel ex-statement" aria-label={t("emp.items")}>
            <div className="ex-st-cover">
              <AssetSlot name="employer-statement-header" alt="" ratio="3/1" tone="sky" rounded="0" fit="contain" anchor="right" priority />
              <span className="ex-st-sent">{L.sent}</span>
            </div>
            <div className="ex-st-head">
              <span className="fx-avatar" data-wash={avatarTone(p.worker.name)} aria-hidden="true">
                {initial}
              </span>
              <div className="ex-st-who">
                <p className="ex-st-name">{p.worker.name}</p>
                <p className="fx-muted">{L.stmt(p.employer.name)}</p>
              </div>
              {emp.pdfUrl ? (
                <a href={emp.pdfUrl} className="fx-pill-btn" target="_blank" rel="noreferrer" style={{ minHeight: 44, padding: "0 16px" }}>
                  <FileIcon /> PDF
                </a>
              ) : null}
            </div>
            <div className="ex-st-total">
              <p className="fx-eyebrow">{t("emp.total")}</p>
              <p className="fx-money" data-paid={!due}>
                {due ? p.balance_display : inr(0)}
              </p>
              {p.amount_paid > 0 ? (
                <p className="ex-paid">
                  <CheckIcon /> <Money value={p.amount_paid} />
                </p>
              ) : null}
              {!due && p.total_due > 0 ? <p className="fx-sub">{t("emp.thanks")}</p> : null}
            </div>

            <div className="ex-ledger-head">
              <p className="fx-eyebrow">{t("emp.items")}</p>
            </div>
            <ul className="ex-ledger">
              {p.items.map((it) => (
                <li key={it.id} className="ex-line" data-kind={it.kind} data-included={it.included_in_total}>
                  <div className="ex-line-row">
                    <span className="ex-line-label">
                      {it.label} {it.is_estimate ? <EstimateTag t={t} /> : null}
                    </span>
                    <span className="ex-line-amt">{it.amount_display}</span>
                  </div>
                  <details className="ex-src">
                    <summary>{t("common.source")}</summary>
                    <div className="ex-src-body">
                      <p>{it.label_en}</p>
                      <p>{it.source}</p>
                    </div>
                  </details>
                </li>
              ))}
            </ul>
            <p className="ex-sum">
              <span>{t("emp.total")}</span>
              <span>{p.balance_display}</span>
            </p>
            {emp.overpaid > 0 ? <p className="fx-muted ex-overpaid">{L.overpaid(inr(emp.overpaid))}</p> : null}
            <div className="ex-foot-row">
              <p className="fx-muted">{L.how}</p>
            </div>
          </section>

        </div>

        <aside className="emp-side">
          {due && upi ? (
            <section className={upi.mobile !== true ? "fx-panel pay" : "ex-pay-bare pay"} aria-label={t("emp.pay_upi")}>
              {upi.mobile !== false ? (
                <a href={upi.link} className="btn btn-primary btn-big">
                  {t("emp.pay_upi")} · {inr(upi.amount)}
                </a>
              ) : (
                <h2 className="fx-h2">{t("emp.pay_upi")}</h2>
              )}
              {upi.mobile !== true ? (
                <div className="ex-qr">
                  {upi.qr ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={upi.qr} alt={t("emp.scan")} width={220} height={220} className="qr" />
                  ) : null}
                  <p className="fx-muted">{t("emp.scan")}</p>
                  <dl className="ex-facts">
                    <div>
                      <dt>{t("emp.upi_id")}</dt>
                      <dd className="mono">{upi.vpa}</dd>
                    </div>
                    <div>
                      <dt>{t("emp.amount")}</dt>
                      <dd>{inr(upi.amount)}</dd>
                    </div>
                  </dl>
                </div>
              ) : null}
            </section>
          ) : null}

          {due ? (
            <>
              {/* "I've paid" is a claim: once made, a calm waiting panel replaces the button until she
                  confirms the money arrived (the page polls, so the badge appears by itself) */}
              {emp.pendingConfirmation ? (
                <section className="fx-panel ex-wait" data-wash="butter" aria-live="polite">
                  <p className="ex-wait-title">
                    <span className="ex-wait-dot" aria-hidden="true" />
                    {L.wait(p.worker.name)}
                  </p>
                  {emp.pendingClaim?.status_text ? <p className="fx-sub fx-wash-ink">{emp.pendingClaim.status_text}</p> : null}
                </section>
              ) : (
                <button type="button" className="fx-pill-btn ex-paid-btn" onClick={() => void emp.pay()} disabled={emp.paying}>
                  <CheckIcon /> {emp.paying ? t("emp.paying") : t("emp.paid_btn")}
                </button>
              )}
              <ErrorNote message={emp.payError} />

              <section className="fx-panel emp-parts" aria-label={t("emp.parts")}>
                <h2 className="fx-h2">{t("emp.parts")}</h2>
                <div className="ex-parts-grid">
                  <button type="button" className="fx-pill-btn" onClick={() => void emp.plan(2)} disabled={emp.planning}>
                    {t("emp.parts_2")}
                  </button>
                  <button type="button" className="fx-pill-btn" onClick={() => void emp.plan(3)} disabled={emp.planning}>
                    {t("emp.parts_3")}
                  </button>
                </div>
                <ErrorNote message={emp.planError} />
                {emp.planRows.length ? (
                  <ol className="ex-plan">
                    {emp.planRows.map((r) => (
                      <li key={r.payment_id} data-status={r.status}>
                        <span className="ex-plan-no" aria-hidden="true">
                          {r.instalment_no}
                        </span>
                        <span className="fx-muted">{shortDate(r.due_date, ui)}</span>
                        <span className="fx-money-sm">
                          {r.instalment_no}/{r.instalments_total} · <Money value={r.amount} />
                        </span>
                      </li>
                    ))}
                  </ol>
                ) : null}
              </section>
            </>
          ) : null}

          {emp.claims.length ? (
            <section className="fx-panel ex-claims" aria-label={L.claims}>
              <h2 className="fx-h2">{L.claims}</h2>
              <ul className="ex-claim-list">
                {emp.claims.map((c) => (
                  <li key={c.id} className="ex-claim" data-state={c.display_state}>
                    <span className="ex-claim-amt">{c.amount_display}</span>
                    <span className="ex-claim-status">{c.status_text}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="fx-panel ex-reply emp-reply" aria-label={t("emp.reply")}>
            <h2 className="fx-h2">{t("emp.reply")}</h2>
            <MicButton
              size="small"
              state={emp.reply.sending ? "busy" : emp.reply.recorder.state}
              level={emp.reply.recorder.level}
              elapsedMs={emp.reply.recorder.elapsedMs}
              disabled={emp.reply.sending}
              handlers={press}
              label={
                emp.reply.sending
                  ? t("emp.reply_sending")
                  : emp.reply.recorder.state === "recording"
                    ? t("emp.reply_stop")
                    : t("emp.reply")
              }
            />
            <form
              className="ex-typed"
              onSubmit={(e) => {
                e.preventDefault();
                const box = e.currentTarget.elements.namedItem("text") as HTMLTextAreaElement | null;
                const text = box?.value.trim() ?? "";
                if (!text) return;
                void emp.reply.sendText(text).then((out) => {
                  if (out && box) box.value = "";
                });
              }}
            >
              <label className="field">
                <span className="field-label">{L.typed}</span>
                <textarea name="text" className="input" rows={2} placeholder={L.typedPh(p.worker.name)} disabled={emp.reply.sending} />
              </label>
              <button type="submit" className="fx-pill-btn" disabled={emp.reply.sending}>
                {L.send}
              </button>
            </form>
            <ErrorNote message={emp.reply.error} />
            {emp.reply.result ? (
              <div className="ex-bubble">
                <p className="fx-muted">{t("emp.reply_sent")}</p>
                <p>{emp.reply.result.transcript}</p>
              </div>
            ) : null}
          </section>
        </aside>

        <div className="ex-different">
          <SomethingDifferentLink token={token} />
        </div>

        <p className="fx-muted emp-foot">
          {p.ai_notice}
        </p>
      </div>
    </Screen>
  );
}
