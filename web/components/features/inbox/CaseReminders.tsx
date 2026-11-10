"use client";

// Case-screen reminders strip (GET /api/cases/{id}/reminders): compact butter cards for what is due now.
//   instalment  her text, his message to share (Web Share / WhatsApp / copy), then "Mark as sent" (mark_sent.path)
//   next_step   no reply for 7+ days: make the next ladder note (action.path, POST) or open the legal-aid pack (GET)
//   promise     a promised date passed unpaid: make the gentle reminder (action.path), then share it
// Nothing is ever sent automatically (auto_send is always false): she shares it herself and marks it herself.
// Renders nothing while loading, on error, or when nothing is due.

import { useEffect, useState } from "react";
import { getReminders, postReminderAction } from "@/lib/api";
import { inr, shortDate } from "@/lib/format";
import { shareMessage, type ShareResult } from "@/lib/share";
import type { UiLang } from "@/lib/i18n";
import type { CaseReminder } from "@/lib/types";
import { useT } from "@/hooks";
import { BellIcon, CheckIcon, ShareIcon } from "@/components/ui/icons";
import { inboxStrings } from "./strings";
import css from "./inbox.module.css";

const HTML_LANG: Record<string, string> = { "te-IN": "te", te: "te", "hi-en": "hi", "hi-IN": "hi", en: "en", "en-IN": "en" };

type Labels = {
  label: string;
  dueToday: string;
  dueAgo: (n: number) => string;
  share: string;
  markSent: string;
  marked: string;
  next: (step: string) => string;
  make: string;
  made: string;
  msgFor: (employer: string) => string;
  copied: string;
  error: string;
};

const REM: Record<UiLang, Labels> = {
  en: {
    label: "Reminders",
    dueToday: "Due today: share it yourself",
    dueAgo: (n) => `${n} ${n === 1 ? "day" : "days"} late: share it yourself`,
    share: "Share",
    markSent: "Mark as sent",
    marked: "Marked as sent",
    next: (s) => `Next: ${s}`,
    make: "Make it now",
    made: "Made. It is in the steps below: share it yourself.",
    msgFor: (e) => `Message for ${e}`,
    copied: "Copied. Paste it in WhatsApp.",
    error: "Could not do that. Try again.",
  },
  te: {
    label: "గుర్తు చేయాల్సినవి",
    dueToday: "ఈ రోజు గడువు: మీరే షేర్ చేయండి",
    dueAgo: (n) => `${n} రోజులు ఆలస్యం: మీరే షేర్ చేయండి`,
    share: "షేర్ చేయండి",
    markSent: "పంపినట్టు గుర్తు పెట్టండి",
    marked: "పంపినట్టు గుర్తు పెట్టాం",
    next: (s) => `తర్వాత: ${s}`,
    make: "ఇప్పుడే తయారు చేయండి",
    made: "తయారైంది. కింద అడుగుల్లో ఉంది: మీరే షేర్ చేయండి.",
    msgFor: (e) => `${e}కి మెసేజ్`,
    copied: "కాపీ అయింది. WhatsAppలో పేస్ట్ చేయండి.",
    error: "కాలేదు. మళ్ళీ ప్రయత్నించండి.",
  },
  "hi-en": {
    label: "Reminders",
    dueToday: "आज की तारीख़: खुद share कीजिए",
    dueAgo: (n) => `${n} दिन देर: खुद share कीजिए`,
    share: "Share कीजिए",
    markSent: "भेजा हुआ mark करें",
    marked: "भेजा हुआ mark हो गया",
    next: (s) => `अगला: ${s}`,
    make: "अभी बनाइए",
    made: "बन गया। नीचे steps में है: खुद share कीजिए।",
    msgFor: (e) => `${e} के लिए message`,
    copied: "Copy हो गया। WhatsApp में paste कीजिए।",
    error: "नहीं हो पाया। फिर कोशिश कीजिए।",
  },
};

/** What a promise reminder POST returns (lib/features/inbox Reminder); only the fields the card shows. */
type MadeReminder = { text?: string; language?: string; share_text?: string };

type CardState = { busy?: boolean; done?: "sent" | "made"; error?: string | null; shared?: ShareResult | null; made?: MadeReminder | null };

export function CaseReminders({
  caseId,
  employer,
  refreshKey,
  onChanged,
}: {
  caseId: number;
  employer: string;
  /** Changes when the case's messages or balance change: refetch, so a sent or settled card drops off. */
  refreshKey?: string;
  /** A ladder note was made from a card: reload the case so the ladder shows it. */
  onChanged?: () => void;
}) {
  const { t, lang } = useT();
  const R = REM[lang] ?? REM.en;
  const S = inboxStrings(lang);
  const [cards, setCards] = useState<CaseReminder[]>([]);
  const [st, setSt] = useState<Record<string, CardState>>({});

  useEffect(() => {
    const ac = new AbortController();
    getReminders(caseId, {}, ac.signal)
      .then((d) => setCards(d.reminders ?? []))
      .catch(() => undefined);
    return () => ac.abort();
  }, [caseId, refreshKey]);

  if (!cards.length) return null;
  const patch = (key: string, next: CardState) => setSt((s) => ({ ...s, [key]: { ...s[key], ...next } }));

  async function act(r: CaseReminder, path: string, then: (out: unknown) => CardState) {
    patch(r.key, { busy: true, error: null });
    try {
      const out = await postReminderAction(path);
      patch(r.key, { busy: false, ...then(out) });
    } catch {
      patch(r.key, { busy: false, error: R.error });
    }
  }

  async function share(r: CaseReminder, text: string) {
    const result = await shareMessage({ text, title: "Baaki" });
    patch(r.key, { shared: result });
  }

  return (
    <section className={css.remStrip} aria-label={R.label}>
      {cards.map((r) => {
        const s = st[r.key] ?? {};
        const due = r.days_overdue > 0 ? R.dueAgo(r.days_overdue) : R.dueToday;
        const amount = typeof r.amount_display === "string" ? r.amount_display : typeof r.amount === "number" ? inr(r.amount) : "";

        let title = r.title;
        let body: string | null = r.text;
        if (r.kind === "next_step") title = R.next(r.title);
        if (r.kind === "promise") {
          title = S.passedTitle;
          body = S.passedBody(amount || S.rest, shortDate(r.due_date, lang));
        }
        // what she shares: the instalment message (his language, with the employer link), or the promise
        // reminder once it is made
        const shareText = r.kind === "promise" ? (s.made?.share_text ?? s.made?.text ?? null) : (r.share_text ?? r.message);
        const preview = r.kind === "promise" ? (s.made?.text ?? null) : r.message;
        const previewLang = r.kind === "promise" ? s.made?.language : r.message_lang;
        const quote = r.kind === "promise" && typeof r.quote === "string" && r.quote ? r.quote : null;

        if (s.done === "sent") {
          return (
            <article key={r.key} className={css.rem} data-done="true" aria-live="polite">
              <p className={css.remTitle}>
                <span className={css.remIcon} aria-hidden="true">
                  <CheckIcon />
                </span>
                {R.marked}
              </p>
              <p className={css.remText}>{title}</p>
            </article>
          );
        }

        return (
          <article key={r.key} className={css.rem} data-kind={r.kind} aria-live="polite">
            <p className={css.remTitle}>
              <span className={css.remIcon} aria-hidden="true">
                <BellIcon />
              </span>
              <span>{title}</span>
            </p>
            <p className={css.remDue}>{due}</p>
            {body ? (
              <p className={css.remText} lang={HTML_LANG[r.text_lang] ?? undefined}>
                {body}
              </p>
            ) : null}
            {quote ? <p className={css.remQuote}>“{quote}”</p> : null}

            {preview ? (
              <details className={css.remMsg}>
                <summary>{R.msgFor(employer)}</summary>
                <p lang={previewLang ? HTML_LANG[previewLang] : undefined}>{preview}</p>
              </details>
            ) : null}

            {s.done === "made" ? <p className={css.remNote}>{R.made}</p> : null}

            <div className={css.remActions}>
              {/* share first (his language), then she marks it herself */}
              {shareText ? (
                <button type="button" className="fx-pill-btn" data-ink onClick={() => void share(r, shareText)}>
                  <ShareIcon /> {R.share}
                </button>
              ) : null}
              {r.kind === "instalment" && r.mark_sent?.path ? (
                <button
                  type="button"
                  className="fx-pill-btn"
                  disabled={s.busy}
                  onClick={() => void act(r, r.mark_sent!.path, () => ({ done: "sent" }))}
                >
                  <CheckIcon /> {R.markSent}
                </button>
              ) : null}
              {r.kind === "next_step" && r.action?.path && s.done !== "made" ? (
                String(r.action.method).toUpperCase() === "GET" ? (
                  <a className="fx-pill-btn" data-ink href={r.action.path} target="_blank" rel="noreferrer">
                    {t("case.legal_pack")}
                  </a>
                ) : (
                  <button
                    type="button"
                    className="fx-pill-btn"
                    data-ink
                    disabled={s.busy}
                    onClick={() =>
                      void act(r, r.action!.path, () => {
                        onChanged?.();
                        return { done: "made" };
                      })
                    }
                  >
                    {s.busy ? t("case.making") : R.make}
                  </button>
                )
              ) : null}
              {r.kind === "promise" && r.action?.path && !s.made ? (
                <button
                  type="button"
                  className="fx-pill-btn"
                  data-ink
                  disabled={s.busy}
                  onClick={() => void act(r, r.action!.path, (out) => ({ made: (out ?? null) as MadeReminder | null }))}
                >
                  <BellIcon /> {S.makeReminder}
                </button>
              ) : null}
            </div>
            {s.shared === "copied" ? <p className={css.remNote}>{R.copied}</p> : null}
            {s.error ? <p className={css.remNote}>{s.error}</p> : null}
          </article>
        );
      })}
    </section>
  );
}
