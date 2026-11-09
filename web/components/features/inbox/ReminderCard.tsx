"use client";

// "Promise passed: remind?" The day after a promised date passes unpaid. One tap makes a gentle reminder in the
// employer's language that quotes their own words back; she shares it herself (Web Share, WhatsApp or copy).

import { useState } from "react";
import { StatusPill } from "@/components/ui/primitives";
import { BellIcon, CheckIcon, ShareIcon } from "@/components/ui/icons";
import { inr, shortDate } from "@/lib/format";
import { shareMessage, type ShareResult } from "@/lib/share";
import type { UiLang } from "@/lib/i18n";
import { makeReminder, setPromise, type InboxPromise, type Reminder } from "@/lib/features/inbox";
import type { InboxStrings } from "./strings";
import css from "./inbox.module.css";

const HTML_LANG: Record<string, string> = { "te-IN": "te", "hi-en": "hi", en: "en" };

export function ReminderCard({
  promise,
  S,
  lang,
  asOf,
  glow,
  onChanged,
}: {
  promise: InboxPromise;
  S: InboxStrings;
  lang: UiLang;
  asOf?: string | null;
  glow?: boolean;
  onChanged: (p: InboxPromise) => void;
}) {
  const [rem, setRem] = useState<Reminder | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [shared, setShared] = useState<ShareResult | null>(null);

  const what = promise.amount != null ? inr(promise.amount) : promise.is_rest ? S.rest : "";
  const due = shortDate(promise.due_date, lang);

  async function make() {
    setBusy(true);
    setErr(null);
    try {
      setRem(await makeReminder(promise.id, asOf));
    } catch {
      setErr(S.error);
    } finally {
      setBusy(false);
    }
  }

  async function mark(status: "kept" | "broken") {
    setBusy(true);
    try {
      onChanged(await setPromise(promise.id, { status, as_of: asOf ?? null }));
    } catch {
      setErr(S.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`${css.reminder} ${css.fresh}`} data-first={glow ? "true" : undefined} aria-live="polite">
        <p className={css.reminderTitle}>
          <span className={css.reminderIcon} aria-hidden="true">
            <BellIcon />
          </span>
          {S.passedTitle}
        </p>
        <p className={css.intro}>{S.passedBody(what, due)}</p>
        {promise.quote ? (
          <div className={css.bubble}>
            <p className={css.bubbleText}>“{promise.quote}”</p>
          </div>
        ) : null}

        {!rem ? (
          <button type="button" className="fx-pill-btn" data-ink style={{ minHeight: 54 }} onClick={() => void make()} disabled={busy}>
            <BellIcon /> {S.makeReminder}
          </button>
        ) : (
          <>
            <div className={css.out}>
              <p className={css.blockLabel}>{S.reminderLabel}</p>
              <p className={css.reminderText} lang={HTML_LANG[rem.language] ?? undefined}>
                {rem.text}
              </p>
              {rem.checks.amounts_ok ? (
                <StatusPill tone="success" dot={false}>
                  <CheckIcon /> {S.checksOk}
                </StatusPill>
              ) : null}
            </div>
            {rem.worker_language !== rem.language ? (
              <details className={css.out} style={{ justifySelf: "stretch", maxWidth: "none" }}>
                <summary className={css.blockLabel}>{S.reminderMine}</summary>
                <p className={css.reminderText} lang={HTML_LANG[rem.worker_language] ?? undefined}>
                  {rem.text_worker_lang}
                </p>
              </details>
            ) : null}
            <button
              type="button"
              className="fx-pill-btn"
              data-ink
              style={{ minHeight: 54 }}
              onClick={async () => setShared(await shareMessage({ text: rem.share_text }))}
            >
              <ShareIcon /> {S.share}
            </button>
            <a className="fx-pill-btn" href={rem.whatsapp_url} target="_blank" rel="noreferrer">
              {S.whatsapp}
            </a>
            {shared === "copied" ? <p className={css.note}>{S.copied}</p> : null}
            <p className={css.note}>{S.youSend}</p>
          </>
        )}

        <div className={css.chipActions}>
          <button type="button" className="fx-pill-btn" onClick={() => void mark("kept")} disabled={busy}>
            {S.markKept}
          </button>
          <button type="button" className="fx-pill-btn" onClick={() => void mark("broken")} disabled={busy}>
            {S.markBroken}
          </button>
        </div>
        {err ? <p className={css.note}>{err}</p> : null}
    </section>
  );
}
