"use client";

// Shared pieces for "Baaki for every promise": the HomeScreen entry card, the promise counter and the chips.

import { useState } from "react";
import { Card } from "@/components/ui/primitives";
import { ArrowRightIcon, CrossIcon } from "@/components/ui/icons";
import { useT } from "@/hooks";
import { inr, shortDate } from "@/lib/format";
import type { UiLang } from "@/lib/i18n";
import { duesLang, type DuesCounter, type DuesPromise, type ParsedItem } from "@/lib/features/dues";
import { DuesArt } from "./DuesArt";
import { duesStrings, type DuesStrings } from "./strings";
import css from "./dues.module.css";

/** Mount point on HomeScreen: `<DuesEntryCard />` (links to /dues). */
export function DuesEntryCard() {
  const { lang } = useT();
  const S = duesStrings(lang);
  return (
    <Card href="/dues" className={css.mount} aria-label={S.mountTitle}>
      <DuesArt kind="vendor" size={56} />
      <span>
        <span className={css.mountTitle}>{S.mountTitle}</span>
        <span className={css.mountBody}>{S.mountBody}</span>
      </span>
      <span className={css.mountArrow} aria-hidden="true">
        <ArrowRightIcon />
      </span>
    </Card>
  );
}

export function initial(name: string): string {
  const n = (name || "?").trim();
  return Array.from(n)[0]?.toUpperCase() ?? "?";
}

/** "Promise made 6 times, broken 6 times, first promised 6 Jul (4 months ago)" with one dot per promise. */
export function PromiseCounter({
  counter,
  promises,
  S,
  lang,
}: {
  counter: DuesCounter;
  promises: DuesPromise[];
  S: DuesStrings;
  lang: UiLang;
}) {
  const none = counter.made === 0;
  const ago = counter.months_ago > 0 ? S.monthsAgo(counter.months_ago) : S.daysAgo(counter.days_ago);
  return (
    <div className={css.counter} data-none={none} aria-live="polite">
      <span className={css.counterNum} aria-hidden="true">
        {counter.broken}/{counter.made}
      </span>
      <div>
        <p className={css.counterText}>{S.counterLine(counter.made, counter.broken)}</p>
        {counter.first_promised ? (
          <p className={css.counterSub}>{S.firstPromised(shortDate(counter.first_promised, lang), ago)}</p>
        ) : null}
        {promises.length ? (
          <div className={css.dots} aria-hidden="true">
            {promises.map((p, i) => (
              <span key={p.id} className={css.dot} data-status={p.status} style={{ animationDelay: `${i * 90}ms` }} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** Editable chips (amount from the parser; the user can fix or remove each one). */
export function Chips({
  items,
  lang,
  S,
  onChange,
}: {
  items: ParsedItem[];
  lang: UiLang;
  S: DuesStrings;
  onChange: (items: ParsedItem[]) => void;
}) {
  const [editing, setEditing] = useState<number | null>(null);
  const dl = duesLang(lang);
  return (
    <ul className={css.chips}>
      {items.map((it, i) => (
        <li key={`${i}-${it.source_text}`} className={css.chip} style={{ animationDelay: `${i * 70}ms` }}>
          {editing === i ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const v = Number(new FormData(e.currentTarget).get("v"));
                if (Number.isFinite(v) && v > 0) onChange(items.map((x, j) => (j === i ? { ...x, amount: v } : x)));
                setEditing(null);
              }}
            >
              <input name="v" className={`input ${css.chipInput}`} type="number" inputMode="numeric" defaultValue={it.amount} autoFocus onBlur={(e) => e.currentTarget.form?.requestSubmit()} />
            </form>
          ) : (
            <button type="button" className="btn-ghost" style={{ display: "inline-flex", gap: 8, border: 0, background: "none", padding: 0, font: "inherit", color: "inherit", cursor: "pointer" }} onClick={() => setEditing(i)} title={S.tapToFix}>
              <span className={css.chipLabel}>{it.display[dl] || it.label}</span>
              <span className={css.chipValue}>{inr(it.amount)}</span>
            </button>
          )}
          <button type="button" className={css.chipX} aria-label={S.remove} onClick={() => onChange(items.filter((_, j) => j !== i))}>
            <CrossIcon />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function NotAdvice({ S }: { S: DuesStrings }) {
  return <p className="footnote">{S.notAdvice}</p>;
}
