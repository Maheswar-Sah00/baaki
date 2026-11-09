"use client";

// Employer side of Hisaab Milao: "Something's different?" Say (or type) what you remember; it goes to her as a
// proposal she accepts or rejects. Nothing changes until she agrees.
import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "@/lib/api";
import {
  getEmployerHisaab,
  noAmountOf,
  propose,
  type HisaabKind,
  type HisaabSummary,
  type ProposeResult,
} from "@/lib/features/hisaab";
import { useRecorder, type Recording } from "@/lib/recorder";
import { ProposalChip } from "./ProposalChip";
import s from "./hisaab.module.css";

const KINDS: { value: HisaabKind | ""; label: string }[] = [
  { value: "", label: "Kaise diya? (auto)" },
  { value: "cash", label: "Cash" },
  { value: "upi", label: "UPI / online" },
  { value: "advance", label: "Advance" },
  { value: "other", label: "Other" },
];

export function HisaabEmployer({ token }: { token: string }) {
  const [data, setData] = useState<HisaabSummary | null>(null);
  const [text, setText] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<HisaabKind | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needAmount, setNeedAmount] = useState(false);
  const [last, setLast] = useState<ProposeResult | null>(null);

  const load = useCallback(() => {
    getEmployerHisaab(token)
      .then(setData)
      .catch((e) => setError(errorMessage(e)));
  }, [token]);

  useEffect(() => {
    load();
    const t = window.setInterval(load, 5000); // her decision lands here
    return () => window.clearInterval(t);
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
          setError(na.message_en);
        } else setError(errorMessage(e));
      } finally {
        setBusy(false);
      }
    },
    [token, text, amount, kind, load],
  );

  const onRecorded = useCallback((r: Recording) => void send(r.blob), [send]);
  const rec = useRecorder({ onRecorded, maxMs: 25_000 });

  return (
    <main className={s.page}>
      <section className={s.card}>
        <h1>Something&apos;s different?</h1>
        <p className={s.muted}>
          Remember it differently? Say it in your own words, for example &ldquo;Maine October mein do hazaar cash diye
          the&rdquo;. {data?.worker.name ?? "She"} hears it in her language and decides. Nothing changes until she
          agrees.
        </p>
        {data && (
          <p>
            Still owed: <span className={s.balance}>{data.balance_display}</span>
          </p>
        )}
        <div className={s.row}>
          <button
            type="button"
            className={`${s.btn} ${rec.state === "recording" ? s.rec : s.primary}`}
            onClick={rec.toggle}
            disabled={busy}
          >
            {rec.state === "recording" ? `Stop (${Math.round(rec.elapsedMs / 1000)} s)` : "Bol ke batayein (tap to speak)"}
          </button>
        </div>
        {rec.error && <p className={s.error}>{rec.error}</p>}
        <p className={s.muted}>Or type it:</p>
        <textarea
          className={s.input}
          rows={2}
          placeholder="Maine October mein 2000 cash diye the"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className={s.row}>
          <input
            className={s.input}
            style={{ maxWidth: 160, borderColor: needAmount ? "var(--error)" : undefined }}
            inputMode="numeric"
            placeholder="₹ amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
          <select className={s.input} style={{ maxWidth: 200 }} value={kind} onChange={(e) => setKind(e.target.value as HisaabKind | "")}>
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={s.btn}
            disabled={busy || (!text.trim() && !amount.trim())}
            onClick={() => void send()}
          >
            {busy ? "Sending…" : "Send"}
          </button>
        </div>
        {error && <p className={s.error}>{error}</p>}
        {last && (
          <div>
            <p className={s.muted}>Heard: &ldquo;{last.proposal.transcript}&rdquo;</p>
            <ProposalChip p={last.proposal} side="employer" />
          </div>
        )}
      </section>

      {data && data.proposals.length > 0 && (
        <section className={s.card}>
          <h2>Your corrections</h2>
          {data.proposals.map((p) => (
            <ProposalChip key={p.id} p={p} side="employer" />
          ))}
          <p className={s.muted}>{data.notice}</p>
        </section>
      )}
    </main>
  );
}

/** Mount on the employer page (/e/[token]): a small link into this flow. */
export function SomethingDifferentLink({ token }: { token: string }) {
  return (
    <a className={s.btn} href={`/hisaab/e/${encodeURIComponent(token)}`} style={{ display: "inline-flex", alignItems: "center" }}>
      Something&apos;s different?
    </a>
  );
}
