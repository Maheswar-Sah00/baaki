"use client";

// Employer page (/e/[token]): public, no login, in the employer's language. Play the voice note,
// see the itemised baaki, pay by UPI (deep link on phones, QR + UPI ID on desktops), "I've paid",
// pay in 2 or 3 parts, or reply by voice. Fair Employer badge after full payment.

import { useEmployerPage, usePressToTalk, useStrings } from "@/hooks";
import { inr, shortDate } from "@/lib/format";
import { uiLangOf } from "@/lib/i18n";
import { shareMessage } from "@/lib/share";
import { BotIcon, CheckIcon, FileIcon, ShareIcon } from "@/components/ui/icons";
import { Card, Confetti, ErrorNote, EstimateTag, Illustration, Loading, MicButton, Money, PlayButton, Screen } from "@/components/ui/primitives";

export function EmployerScreen({ token }: { token: string }) {
  const emp = useEmployerPage(token);
  const ui = uiLangOf(emp.page?.employer.language);
  const t = useStrings(ui);
  const press = usePressToTalk(emp.reply.recorder, { disabled: emp.reply.sending });

  if (emp.loading) {
    return (
      <Screen safetyLink={false}>
        <Loading label={t("common.loading")} />
      </Screen>
    );
  }
  if (!emp.page) {
    return (
      <Screen safetyLink={false}>
        <ErrorNote message={emp.notFound ? t("emp.not_found") : emp.error} onRetry={emp.notFound ? undefined : emp.refresh} retryLabel={t("common.retry")} />
      </Screen>
    );
  }

  const p = emp.page;
  const due = p.balance > 0.5;
  const upi = emp.upi;

  return (
    <Screen title={t("emp.title", { name: p.worker.name })} safetyLink={false} className="employer-screen">
      <div lang={p.employer.language === "te-IN" ? "te" : p.employer.language === "hi-en" ? "hi" : "en"} className="emp-layout">
        <div className="emp-main stack">
          {emp.badge ? (
            <Card as="section" tone="gradient" className="badge-card" aria-label={t("emp.fair")}>
              <Confetti pieces={18} />
              <Illustration name="handshake" size={180} className="badge-card-ill" />
              <p className="badge-card-title">{t("emp.fair")}</p>
              <p className="badge-card-text">{emp.badge.text}</p>
              <button type="button" className="btn" onClick={() => void shareMessage({ text: emp.badge!.share_text, title: "Fair Employer" })}>
                <ShareIcon /> {t("emp.share_badge")}
              </button>
            </Card>
          ) : null}

          {emp.audioUrl ? (
            <Card as="section" tone={emp.badge ? "default" : "glow"} className="voice-note">
              {!emp.badge ? <Illustration name="send" size={170} className="voice-note-ill" /> : null}
              <PlayButton
                state={emp.player.state}
                active={emp.player.isCurrent(emp.audioUrl)}
                progress={emp.player.progress}
                onClick={() => void emp.play()}
                label={t("emp.play")}
              />
              <p className="hint voice-note-notice">
                <BotIcon /> {t("emp.ai_notice")}
              </p>
            </Card>
          ) : null}

          <section className="card receipt emp-receipt" aria-label={t("emp.items")}>
            <div className="receipt-head">
              <span className="receipt-avatar" aria-hidden="true">
                {p.worker.name.slice(0, 1).toUpperCase()}
              </span>
              <div className="receipt-head-text">
                <p className="total-label">{t("emp.total")}</p>
                <p className="total-value" data-paid={!due}>
                  {due ? p.balance_display : inr(0)}
                </p>
                {p.amount_paid > 0 ? (
                  <p className="meta emp-paid">
                    <CheckIcon /> <Money value={p.amount_paid} />
                  </p>
                ) : null}
              </div>
            </div>
            {!due && p.total_due > 0 ? <p className="thanks">{t("emp.thanks")}</p> : null}

            <h2 className="section-title receipt-section">{t("emp.items")}</h2>
            <ul className="items receipt-items">
              {p.items.map((it) => (
                <li key={it.id} className="item" data-kind={it.kind} data-included={it.included_in_total}>
                  <div className="item-row">
                    <span className="item-label">
                      {it.label} {it.is_estimate ? <EstimateTag t={t} /> : null}
                    </span>
                    <span className="money">{it.amount_display}</span>
                  </div>
                  <details className="item-source">
                    <summary>{t("common.source")}</summary>
                    <p>{it.label_en}</p>
                    <p className="meta">{it.source}</p>
                  </details>
                </li>
              ))}
            </ul>
            {emp.pdfUrl ? (
              <a href={emp.pdfUrl} className="btn btn-small btn-ghost receipt-pdf" target="_blank" rel="noreferrer">
                <FileIcon /> PDF
              </a>
            ) : null}
          </section>
        </div>

        <aside className="emp-side stack">
          {due && upi ? (
            <section className="card pay" aria-label={t("emp.pay_upi")}>
              {upi.mobile !== false ? (
                <a href={upi.link} className="btn btn-primary btn-big">
                  {t("emp.pay_upi")} · {inr(upi.amount)}
                </a>
              ) : (
                <h2 className="card-title">{t("emp.pay_upi")}</h2>
              )}
              {upi.mobile !== true ? (
                <div className="upi-desktop">
                  {upi.qr ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={upi.qr} alt={t("emp.scan")} width={220} height={220} className="qr" />
                  ) : null}
                  <p className="hint">{t("emp.scan")}</p>
                  <dl className="facts upi-facts">
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
              <button type="button" className="btn btn-yes btn-big" onClick={() => void emp.pay()} disabled={emp.paying}>
                <CheckIcon /> {emp.paying ? t("emp.paying") : t("emp.paid_btn")}
              </button>
              <ErrorNote message={emp.payError} />

              <section className="card emp-parts" aria-label={t("emp.parts")}>
                <h2 className="card-title">{t("emp.parts")}</h2>
                <div className="emp-parts-grid">
                  <button type="button" className="btn btn-big" onClick={() => void emp.plan(2)} disabled={emp.planning}>
                    {t("emp.parts_2")}
                  </button>
                  <button type="button" className="btn btn-big" onClick={() => void emp.plan(3)} disabled={emp.planning}>
                    {t("emp.parts_3")}
                  </button>
                </div>
                <ErrorNote message={emp.planError} />
                {emp.planRows.length ? (
                  <ol className="plan-list">
                    {emp.planRows.map((r) => (
                      <li key={r.payment_id} className="plan-row" data-status={r.status}>
                        <span className="plan-no" aria-hidden="true">
                          {r.instalment_no}
                        </span>
                        <span className="plan-text">
                          <span className="plan-amount">
                            {r.instalment_no}/{r.instalments_total}: <Money value={r.amount} />
                          </span>
                          <span className="meta">{shortDate(r.due_date, ui)}</span>
                        </span>
                      </li>
                    ))}
                  </ol>
                ) : null}
              </section>
            </>
          ) : null}

          <section className="card emp-reply" aria-label={t("emp.reply")}>
            <h2 className="card-title">{t("emp.reply")}</h2>
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
            <ErrorNote message={emp.reply.error} />
            {emp.reply.result ? (
              <div className="reply reply-bubble">
                <p className="meta">{t("emp.reply_sent")}</p>
                <p>{emp.reply.result.transcript}</p>
              </div>
            ) : null}
          </section>
        </aside>

        <p className="footnote emp-foot">{p.ai_notice}</p>
      </div>
    </Screen>
  );
}
