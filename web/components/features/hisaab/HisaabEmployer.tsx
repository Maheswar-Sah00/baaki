"use client";

// Employer side of Hisaab Milao (/hisaab/e/[token]): "Something's different?" He says (or types) what he
// remembers; it goes to the worker as a proposal she accepts or rejects. Nothing changes until she agrees.
// Chrome is in the employer's language (like /e/[token]); amounts, months and statuses come from the backend.
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { errorMessage } from "@/lib/api";
import {
  getEmployerHisaab,
  noAmountOf,
  propose,
  type HisaabKind,
  type HisaabSummary,
  type ProposeResult,
} from "@/lib/features/hisaab";
import { formatTimer, useRecorder, type Recording } from "@/lib/recorder";
import Link from "next/link";
import { uiLangOf, type UiLang } from "@/lib/i18n";
import { ErrorNote, MoneyFigure, Screen, SkeletonCard, Waveform } from "@/components/ui/primitives";
import { ArrowRightIcon, ChevronRightIcon, LockIcon, MicIcon, PenIcon, StopIcon } from "@/components/ui/icons";
import { ProposalChip } from "./ProposalChip";
import { HTML_LANG, employerStrings } from "./strings";
import s from "./hisaab.module.css";

const KINDS: (HisaabKind | "")[] = ["", "cash", "upi", "advance", "other"];

export function HisaabEmployer({ token }: { token: string }) {
  const [data, setData] = useState<HisaabSummary | null>(null);
  const [text, setText] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<HisaabKind | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needAmount, setNeedAmount] = useState(false);
  const [last, setLast] = useState<ProposeResult | null>(null);
  const ui = uiLangOf(data?.employer.language);
  const E = employerStrings(ui);
  const worker = data?.worker.name ?? "";

  const load = useCallback(() => {
    getEmployerHisaab(token)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [token]);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 5000); // her decision lands here
    return () => window.clearInterval(id);
  }, [load]);

  const send = useCallback(
    async (audio?: Blob) => {
      setBusy(true);
      setError(null);
      try {
        const r = await propose(token, {
          audio,
          text: text.trim() || undefined,
          amount: amount.trim() || undefined,
          kind: kind || undefined,
        });
        setLast(r);
        setNeedAmount(false);
        setText("");
        setAmount("");
        load();
      } catch (e) {
        const na = noAmountOf(e);
        if (na) {
          setNeedAmount(true);
          if (na.transcript) setText(na.transcript); // keep his words; he only types the amount
          setError(na.message || na.message_en);
        } else setError(errorMessage(e));
      } finally {
        setBusy(false);
      }
    },
    [token, text, amount, kind, load],
  );

  const onRecorded = useCallback((r: Recording) => void send(r.blob), [send]);
  const rec = useRecorder({ onRecorded, maxMs: 25_000 });
  const recording = rec.state === "recording";
  const htmlLang = HTML_LANG[ui];

  return (
    <Screen title={worker ? E.title(worker) : undefined} safetyLink={false} className={`fx ${s.screen} ${s.wide}`}>
      <div className={s.empGrid} lang={htmlLang}>
        <header className={`${s.head} ${s.aHead}`}>
          <p className="fx-eyebrow">{E.eyebrow}</p>
          <h1 className={`fx-h ${s.h}`}>
            {E.lead} <em>{E.accent}</em>
          </h1>
          <p className="fx-sub">{worker ? E.sub(worker) : null}</p>
        </header>

        <div className={s.aBal}>
          {data ? (
            <section className={s.statement} aria-label={E.stillOwed(worker)}>
              <div className={s.stTop}>
                <span className="fx-avatar" data-wash="peach" aria-hidden="true">
                  {Array.from(worker)[0]?.toUpperCase()}
                </span>
                <div className={s.stWho}>
                  <p className={s.stName}>{worker}</p>
                  <p className="fx-muted">{E.stillOwed(worker)}</p>
                </div>
                <span />
              </div>
              <p className={s.stFigure} aria-live="polite">
                <MoneyFigure value={data.balance} size="xl" />
              </p>
              <p className={s.owedLine}>
                <LockIcon /> {E.untilAgree}
              </p>
            </section>
          ) : error ? (
            <ErrorNote message={error} onRetry={load} />
          ) : (
            <SkeletonCard />
          )}
        </div>

        <section className={`${s.composer} ${s.aComp}`} aria-label={E.words}>
          <button
            type="button"
            className={s.recBtn}
            data-state={rec.state}
            onClick={rec.toggle}
            disabled={busy}
            aria-pressed={recording}
            style={{ "--level": rec.level } as CSSProperties}
          >
            <span className={s.recDot} aria-hidden="true">
              {recording ? <StopIcon /> : <MicIcon />}
            </span>
            <span className={s.recText} aria-live="polite">
              {recording ? E.stop(formatTimer(rec.elapsedMs)) : busy ? E.sending : E.speak}
            </span>
            <Waveform active={recording} level={recording ? Math.max(0.25, rec.level) : 0.2} bars={12} className={s.recWave} />
          </button>
          <p className={s.example}>{E.example}</p>
          <ErrorNote message={rec.error} />

          <p className={s.divider}>
            <span>{E.orType}</span>
          </p>

          <label className={s.field}>
            <span className={s.fieldLabel}>{E.words}</span>
            <textarea className={s.textarea} rows={2} placeholder={E.placeholder} value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          <label className={s.field}>
            <span className={s.fieldLabel}>{E.amount}</span>
            <span className={s.amountWrap} data-invalid={needAmount}>
              <span aria-hidden="true">₹</span>
              <input
                className={s.input}
                inputMode="numeric"
                placeholder="2,000"
                value={amount}
                aria-invalid={needAmount || undefined}
                onChange={(e) => setAmount(e.target.value)}
              />
            </span>
          </label>
          <fieldset className={s.kinds}>
            <legend className={s.fieldLabel}>{E.how}</legend>
            <div className={s.kindRow}>
              {KINDS.map((k) => (
                <button key={k || "auto"} type="button" className={s.kind} aria-pressed={kind === k} onClick={() => setKind(k)}>
                  {E.kinds[k]}
                </button>
              ))}
            </div>
          </fieldset>
          <button type="button" className={s.send} disabled={busy || (!text.trim() && !amount.trim())} onClick={() => void send()}>
            {busy ? E.sending : E.send(worker || "…")} {busy ? null : <ArrowRightIcon />}
          </button>
          {data ? <ErrorNote message={error} /> : null}
          {last ? (
            <div className={s.heard} role="status">
              <p className="fx-eyebrow">{E.heard}</p>
              <p className={s.heardText}>&ldquo;{last.proposal.transcript}&rdquo;</p>
              <ProposalChip p={last.proposal} side="employer" lang={ui} />
            </div>
          ) : null}
        </section>

        <section className={`${s.section} ${s.aList}`} aria-label={E.yours}>
          <h2 className="section-title" style={{ margin: 0 }}>
            {E.yours}
          </h2>
          {data && data.proposals.length > 0 ? (
            <div className={s.ledger}>
              <ul className={s.ledgerList}>
                {data.proposals.map((p) => (
                  <li key={p.id}>
                    <ProposalChip p={p} side="employer" lang={ui} />
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="fx-muted">{E.none}</p>
          )}
          <p className="fx-muted">{E.notice}</p>
        </section>
      </div>
    </Screen>
  );
}

/**
 * Mount on the employer page (/e/[token]): a quiet secondary link into this flow, under the statement.
 * `lang` = the employer's language (e.g. uiLangOf(page.employer.language)); defaults to English.
 */
export function SomethingDifferentLink({ token, lang = "en" }: { token: string; lang?: UiLang }) {
  const E = employerStrings(lang);
  return (
    <Link className={s.somethingLink} href={`/hisaab/e/${encodeURIComponent(token)}`} lang={HTML_LANG[lang]}>
      <span aria-hidden="true">
        <PenIcon />
      </span>
      {E.lead} {E.accent}
      <ChevronRightIcon />
    </Link>
  );
}
