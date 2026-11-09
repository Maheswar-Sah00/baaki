"use client";

// "Sharma ji's phone": the cached voice note, the itemised dues, UPI switched off, Mark as paid.

import type { SandboxView } from "@/lib/features/sandbox";

import { Banner, box, btn } from "./Banner";

type Props = {
  view: SandboxView;
  paying: boolean;
  payError: string | null;
  onPlayed: () => void;
  onPay: () => void;
};

export function EmployerPhone({ view, paying, payError, onPlayed, onPay }: Props) {
  const included = view.items.filter((i) => i.included_in_total);
  const shown = view.items.filter((i) => !i.included_in_total);
  return (
    <section style={box} aria-label="Sharma ji's phone">
      <h2 style={{ fontSize: 18, margin: "0 0 8px" }}>Sharma ji&apos;s phone</h2>
      <Banner />

      <h3 style={h3}>Voice note from {view.worker.name}</h3>
      {view.voice_note.available && view.voice_note.audio_url ? (
        <>
          <audio controls preload="none" src={view.voice_note.audio_url} onPlay={onPlayed} style={{ width: "100%" }} />
          <p style={small}>{view.voice_note.label}</p>
        </>
      ) : (
        <p style={{ ...small, color: "var(--text-2)" }}>
          {view.voice_note.label}. {view.voice_note.reason}
        </p>
      )}
      {view.message?.text && (
        <p lang="hi" style={{ background: "var(--surface-2)", borderRadius: "var(--r-md, 12px)", padding: 12, margin: "8px 0" }}>
          {view.message.text}
        </p>
      )}
      <p style={small}>{view.ai_notice}</p>

      <h3 style={h3}>What is owed</h3>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {included.map((i) => (
          <li key={i.id} style={row}>
            <span>
              {i.label_en}
              {i.due_date ? <span style={small}> · due {i.due_date}</span> : null}
            </span>
            <strong>{i.amount_display}</strong>
          </li>
        ))}
        <li style={{ ...row, borderBottom: "none", fontSize: 18 }}>
          <span>{view.paid ? "Still due" : "Total due"}</span>
          <strong>{view.balance_display}</strong>
        </li>
      </ul>
      {shown.map((i) => (
        <p key={i.id} style={small}>
          {i.label_en}: {i.amount_display} {i.is_estimate ? "(estimate, not added to the total)" : ""}
        </p>
      ))}

      <p style={{ ...small, marginTop: 12, padding: 8, border: "1px dashed var(--line-2)", borderRadius: 8 }}>
        {view.upi.label}
      </p>
      <p style={{ ...small, color: "var(--muted)" }}>{view.reply.label}</p>

      {view.paid ? (
        <p style={{ color: "var(--success)", fontWeight: 600 }}>
          Marked as paid.{view.badge ? ` ${view.badge.text_en}` : ""}
        </p>
      ) : (
        <button type="button" onClick={onPay} disabled={paying} style={{ ...btn, width: "100%", marginTop: 8 }}>
          {paying ? "Marking as paid…" : "Mark as paid"}
        </button>
      )}
      {payError && (
        <p role="alert" style={{ color: "var(--error)" }}>
          {payError}
        </p>
      )}
    </section>
  );
}

const h3: React.CSSProperties = { fontSize: 15, margin: "16px 0 6px" };
const small: React.CSSProperties = { fontSize: 13, color: "var(--muted)", margin: "4px 0" };
const row: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  padding: "8px 0",
  borderBottom: "1px solid var(--line)",
};
