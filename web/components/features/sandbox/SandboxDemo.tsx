"use client";

// V04 "Be Sharma ji": a public, synthetic employer sandbox. The viewer is Sharma ji: plays Lakshmi's
// cached voice note, sees the itemised dues and taps "Mark as paid"; Lakshmi's phone (polling) shows
// "Paisa aa gaya!" and plays the cached clip. No install, no real money, no live AI calls.
// Functional only: the redesign session owns the visual polish.

import { useCallback, useEffect, useState } from "react";

import {
  SandboxError,
  markPaid,
  markPlayed,
  openSandbox,
  rememberSid,
  type SandboxPaid,
  type SandboxView,
} from "@/lib/features/sandbox";

import { Banner, box, btn } from "./Banner";
import { EmployerPhone } from "./EmployerPhone";
import { WorkerPhone } from "./WorkerPhone";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string; canRetry: boolean }
  | { kind: "ready"; view: SandboxView };

export function SandboxDemo() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  const start = useCallback(async (fresh: boolean) => {
    setState({ kind: "loading" });
    setPayError(null);
    try {
      setState({ kind: "ready", view: await openSandbox(fresh) });
    } catch (e) {
      const err = e instanceof SandboxError ? e : null;
      const wait = err?.retryAfter ? ` (about ${Math.ceil(err.retryAfter / 60)} min)` : "";
      setState({ kind: "error", message: (err?.message ?? "Something went wrong.") + wait, canRetry: err?.status !== 429 });
    }
  }, []);

  useEffect(() => {
    void start(false);
  }, [start]);

  const onPlayed = useCallback((sid: string) => {
    markPlayed(sid).catch(() => undefined);
  }, []);

  const onPay = useCallback(async (view: SandboxView) => {
    setPaying(true);
    setPayError(null);
    try {
      const res: SandboxPaid = await markPaid(view.sandbox_id);
      setState({
        kind: "ready",
        view: { ...view, paid: true, balance: res.balance, balance_display: res.balance_display,
          amount_paid: res.amount_paid, status: res.status, badge: res.badge ?? view.badge },
      });
    } catch (e) {
      if (e instanceof SandboxError && e.gone) {
        rememberSid(null);
        setState({ kind: "error", message: e.message, canRetry: true });
      } else {
        setPayError(e instanceof Error ? e.message : "Could not mark as paid.");
      }
    } finally {
      setPaying(false);
    }
  }, []);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "16px", color: "var(--text)", fontFamily: "var(--font-sans)" }}>
      <Banner />
      <h1 style={{ fontSize: 26, margin: "16px 0 4px" }}>Be Sharma ji</h1>
      <p style={{ color: "var(--text-2)", margin: "0 0 16px" }}>
        You are the employer. Lakshmi has sent you a polite voice note about her unpaid salary. Listen, check the
        dues, and pay. Nothing here is real: no money moves and no live AI is called.
      </p>

      {state.kind === "loading" && <div style={box}>Setting up your demo…</div>}

      {state.kind === "error" && (
        <div style={{ ...box, borderColor: "var(--error)" }} role="alert">
          <p style={{ margin: "0 0 8px" }}>{state.message}</p>
          {state.canRetry && (
            <button type="button" onClick={() => void start(true)} style={btn}>
              Start a new demo
            </button>
          )}
        </div>
      )}

      {state.kind === "ready" && (
        <>
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            <EmployerPhone
              view={state.view}
              paying={paying}
              payError={payError}
              onPlayed={() => onPlayed(state.view.sandbox_id)}
              onPay={() => void onPay(state.view)}
            />
            <WorkerPhone sid={state.view.sandbox_id} />
          </div>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 16 }}>
            This demo expires in about {Math.max(1, Math.round(state.view.expires_in_s / 60))} minutes.{" "}
            <button type="button" onClick={() => void start(true)} style={linkBtn}>
              Start over
            </button>
          </p>
        </>
      )}
    </main>
  );
}

const linkBtn: React.CSSProperties = {
  background: "none",
  border: "none",
  padding: 0,
  color: "var(--accent-text)",
  textDecoration: "underline",
  cursor: "pointer",
  font: "inherit",
};
