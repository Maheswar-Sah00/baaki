"use client";

// One promise from the employer's reply: amount + date + status pill. Before she relies on it, she
// confirms the read-back ("Is this right?") or fixes the date / amount. Kept / not kept are her taps.

import { useState } from "react";
import { StatusPill } from "@/components/ui/primitives";
import { CheckIcon } from "@/components/ui/icons";
import { inr, shortDate } from "@/lib/format";
import type { UiLang } from "@/lib/i18n";
import { promiseTone, setPromise, type InboxPromise } from "@/lib/features/inbox";
import type { InboxStrings } from "./strings";
import css from "./inbox.module.css";

export function PromiseChip({
  promise,
  S,
  lang,
  asOf,
  onChanged,
}: {
  promise: InboxPromise;
  S: InboxStrings;
  lang: UiLang;
  asOf?: string | null;
  onChanged: (p: InboxPromise) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [date, setDate] = useState(promise.due_date);
  const [amount, setAmount] = useState(promise.amount != null ? String(promise.amount) : "");

  const p = promise;
  const what = p.amount != null ? inr(p.amount) : p.is_rest ? S.rest : S.amountNotSaid;
  const when =
    p.precision === "week" && p.range_start
      ? S.weekOf(shortDate(p.range_start, lang), shortDate(p.due_date, lang))
      : S.by(shortDate(p.due_date, lang));

  async function patch(body: Parameters<typeof setPromise>[1]) {
    setBusy(true);
    setErr(null);
    try {
      const next = await setPromise(p.id, { ...body, as_of: asOf ?? null });
      onChanged(next);
      setEditing(false);
    } catch {
      setErr(S.error);
    } finally {
      setBusy(false);
    }
  }

  const open = p.status === "pending" || p.status === "passed";

  return (
    <div className={css.chip} data-status={p.status}>
      <div className={css.chipTop}>
        <p className={css.chipMain}>
          <span className={css.chipAmount}>{what}</span>
          <span className={css.chipDate}>{when}</span>
        </p>
        <StatusPill tone={promiseTone(p.status)}>{S.status[p.status]}</StatusPill>
      </div>
      {p.phrase ? (
        <p className={css.chipSub}>
          {S.promise}: “{p.phrase}”{p.confirmed ? " · ✓" : ""}
        </p>
      ) : null}

      {editing ? (
        <div className={css.edit}>
          <div className={css.twoCol}>
            <label className="field">
              <span className="field-label">{S.dateLabel}</span>
              <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">{S.amountLabel}</span>
              <input
                className="input"
                type="number"
                inputMode="numeric"
                min={1}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
          </div>
          <div className={css.chipActions}>
            <button
              type="button"
              className="btn btn-yes"
              disabled={busy || !date}
              onClick={() => {
                const n = Number(amount);
                void patch({
                  confirmed: true,
                  due_date: date !== p.due_date ? date : undefined,
                  amount: amount && Number.isFinite(n) && n > 0 && n !== p.amount ? n : undefined,
                });
              }}
            >
              {S.save}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)} disabled={busy}>
              {S.cancel}
            </button>
          </div>
        </div>
      ) : null}

      {!editing && open && !p.confirmed && p.status === "pending" ? (
        <>
          <p className={css.chipSub}>{S.confirmQ}</p>
          <div className={css.chipActions}>
            <button type="button" className="btn btn-yes" disabled={busy} onClick={() => void patch({ confirmed: true })}>
              <CheckIcon /> {S.yes}
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => setEditing(true)}>
              {S.fix}
            </button>
          </div>
        </>
      ) : null}

      {!editing && open && (p.confirmed || p.status === "passed") ? (
        <div className={css.chipActions}>
          <button type="button" className="btn btn-small" disabled={busy} onClick={() => void patch({ status: "kept" })}>
            {S.markKept}
          </button>
          {p.status === "passed" ? (
            <button type="button" className="btn btn-small" disabled={busy} onClick={() => void patch({ status: "broken" })}>
              {S.markBroken}
            </button>
          ) : (
            <button type="button" className="btn btn-small btn-ghost" disabled={busy} onClick={() => setEditing(true)}>
              {S.fix}
            </button>
          )}
        </div>
      ) : null}
      {err ? <p className={css.note}>{err}</p> : null}
    </div>
  );
}
