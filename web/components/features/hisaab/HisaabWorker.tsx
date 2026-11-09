"use client";

// Worker side of Hisaab Milao: hear what the employer said in her language, then ✓ (accept) or ✗ (reject).
// Accept records it as a payment "said by the employer, accepted by her"; reject keeps it visible as disputed.
import { useCallback, useEffect, useState } from "react";
import { errorMessage, mediaUrl } from "@/lib/api";
import { decide, getCaseHisaab, type HisaabProposal, type HisaabSummary } from "@/lib/features/hisaab";
import { ProposalChip } from "./ProposalChip";
import s from "./hisaab.module.css";

function Pending({ p, onDone }: { p: HisaabProposal; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const go = async (d: "accept" | "reject") => {
    setBusy(true);
    setError(null);
    try {
      await decide(p.id, d);
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={s.card}>
      <ProposalChip p={p} side="worker" />
      <p style={{ fontSize: "1.15rem" }}>{p.readback.text}</p>
      <audio controls preload="none" src={mediaUrl(p.readback.audio_url) ?? undefined} style={{ width: "100%" }} />
      <p className={s.muted}>
        {p.said_by_label}: &ldquo;{p.transcript}&rdquo;
      </p>
      {p.exceeds_balance && <p className={s.error}>This is more than what is still owed, so it can&apos;t be accepted.</p>}
      <div className={s.row}>
        <button type="button" className={`${s.btn} ${s.yes}`} disabled={busy || p.exceeds_balance} onClick={() => void go("accept")}>
          ✓ Avunu / Yes
        </button>
        <button type="button" className={`${s.btn} ${s.no}`} disabled={busy} onClick={() => void go("reject")}>
          ✗ Kaadu / No
        </button>
      </div>
      {error && <p className={s.error}>{error}</p>}
    </div>
  );
}

export function HisaabWorker({ caseId }: { caseId: string }) {
  const [data, setData] = useState<HisaabSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getCaseHisaab(caseId)
      .then(setData)
      .catch((e) => setError(errorMessage(e)));
  }, [caseId]);

  useEffect(() => {
    load();
    const t = window.setInterval(load, 5000); // a new proposal from the employer lands here
    return () => window.clearInterval(t);
  }, [load]);

  if (error && !data) return <main className={s.page}><p className={s.error}>{error}</p></main>;
  if (!data) return <main className={s.page}><p className={s.muted}>Loading…</p></main>;
  const pending = data.proposals.filter((p) => p.status === "proposed");
  const decided = data.proposals.filter((p) => p.status !== "proposed");
  return (
    <main className={s.page}>
      <section className={s.card}>
        <h1>Hisaab Milao</h1>
        <p className={s.muted}>{data.employer.name} · baaki</p>
        <p className={s.balance}>{data.balance_display}</p>
        <p className={s.muted}>{data.notice}</p>
      </section>
      {pending.map((p) => (
        <Pending key={p.id} p={p} onDone={load} />
      ))}
      {pending.length === 0 && <p className={s.muted}>No corrections waiting.</p>}
      {decided.length > 0 && (
        <section className={s.card}>
          <h2>Decided</h2>
          {decided.map((p) => (
            <ProposalChip key={p.id} p={p} side="worker" />
          ))}
        </section>
      )}
    </main>
  );
}

/** Mount on the case screen: a small card with the pending count, linking to /hisaab/[caseId]. */
export function HisaabCaseCard({ caseId }: { caseId: number | string }) {
  const [data, setData] = useState<HisaabSummary | null>(null);
  useEffect(() => {
    getCaseHisaab(caseId).then(setData).catch(() => setData(null));
  }, [caseId]);
  if (!data || data.proposals.length === 0) return null;
  return (
    <a className={s.card} href={`/hisaab/${encodeURIComponent(String(caseId))}`} style={{ textDecoration: "none", color: "inherit" }}>
      <strong>{data.pending > 0 ? `${data.employer.name} remembers it differently (${data.pending})` : "Corrections"}</strong>
      {data.proposals.slice(0, 2).map((p) => (
        <ProposalChip key={p.id} p={p} side="worker" />
      ))}
    </a>
  );
}
