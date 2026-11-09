"use client";

// V04 "Be Sharma ji" (/try/employer): a public, synthetic employer sandbox. The visitor is Sharma ji: plays Lakshmi's
// cached voice note, sees what is owed and taps "Mark as paid"; Lakshmi's phone (polling) shows "Paisa aa gaya!" and
// plays the cached clip. Two real-looking phones side by side on desktop, stacked on phones. No install, no real money,
// no live AI calls.

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  SandboxError,
  markPaid,
  markPlayed,
  openSandbox,
  rememberSid,
  type SandboxPaid,
  type SandboxView,
} from "@/lib/features/sandbox";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { Logo } from "@/components/ui/Logo";
import { Skeleton, ThemeToggle } from "@/components/ui/primitives";
import { ArrowRightIcon } from "@/components/ui/icons";
import { Banner } from "./Banner";
import { EmployerPhone } from "./EmployerPhone";
import { WorkerPhone } from "./WorkerPhone";
import css from "./sandbox.module.css";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string; canRetry: boolean }
  | { kind: "ready"; view: SandboxView };

function failed(e: unknown): State {
  const err = e instanceof SandboxError ? e : null;
  const wait = err?.retryAfter ? ` (about ${Math.ceil(err.retryAfter / 60)} min)` : "";
  return { kind: "error", message: (err?.message ?? "Something went wrong.") + wait, canRetry: err?.status !== 429 };
}

function Device({ label, sub, children }: { label: string; sub: string; children: ReactNode }) {
  return (
    <figure className={css.device}>
      <div className={css.phone}>
        <span className={css.island} aria-hidden="true" />
        <div className={css.screen}>
          <div className={css.status} aria-hidden="true">
            <span>9:41</span>
            <span className={css.statusIcons}>
              <i />
              <i />
              <i />
              <b />
            </span>
          </div>
          {children}
        </div>
      </div>
      <figcaption className={css.caption}>
        <strong>{label}</strong> {sub}
      </figcaption>
    </figure>
  );
}

export function SandboxDemo() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  // First visit: reuse this browser's live sandbox or start one (state is set only when the request settles).
  useEffect(() => {
    let alive = true;
    openSandbox(false)
      .then((view) => alive && setState({ kind: "ready", view }))
      .catch((e: unknown) => alive && setState(failed(e)));
    return () => {
      alive = false;
    };
  }, []);

  const start = useCallback(async (fresh: boolean) => {
    setState({ kind: "loading" });
    setPayError(null);
    try {
      setState({ kind: "ready", view: await openSandbox(fresh) });
    } catch (e) {
      setState(failed(e));
    }
  }, []);

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
        view: {
          ...view,
          paid: true,
          balance: res.balance,
          balance_display: res.balance_display,
          amount_paid: res.amount_paid,
          status: res.status,
          badge: res.badge ?? view.badge,
        },
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
    <main className={css.page}>
      <div className={css.sky} aria-hidden="true" />
      <header className={css.nav}>
        <Link href="/" className={css.brand} aria-label="Baaki home">
          <Logo size={30} telugu={false} />
        </Link>
        <div className={css.navRight}>
          <span className={css.navTag}>Sandbox</span>
          <ThemeToggle />
        </div>
      </header>

      <section className={css.hero}>
        <div className={css.heroText}>
          <Banner />
          <h1 className={css.title}>
            Be Sharma ji <em>for a minute.</em>
          </h1>
          <p className={css.sub}>
            You are the employer. Lakshmi sent you a polite voice note about her unpaid salary. Listen, check what is
            owed, and pay.
          </p>
        </div>
        <div className={css.heroArt}>
          <AssetSlot name="can-do-letter-voice" alt="" ratio="1600/753" tone="sky" fit="contain" rounded="0" priority />
        </div>
      </section>

      {state.kind === "loading" ? (
        <div className={css.stage} role="status" aria-label="Setting up your demo…">
          {[0, 1].map((k) => (
            <Device key={k} label={k ? "Lakshmi" : "You"} sub={k ? "· live" : "· Sharma ji"}>
              <div className={css.app}>
                <Skeleton height={20} width="50%" />
                <Skeleton height={96} radius={20} />
                <Skeleton height={56} radius={999} />
                <Skeleton lines={4} height={14} />
              </div>
            </Device>
          ))}
        </div>
      ) : null}

      {state.kind === "error" ? (
        <div className={css.errorCard} role="alert">
          <p>{state.message}</p>
          {state.canRetry ? (
            <button type="button" className={css.payBtn} onClick={() => void start(true)}>
              Start a new demo
            </button>
          ) : null}
        </div>
      ) : null}

      {state.kind === "ready" ? (
        <>
          <div className={css.stage}>
            <Device label="You" sub="· Sharma ji's phone">
              <EmployerPhone
                view={state.view}
                paying={paying}
                payError={payError}
                onPlayed={() => onPlayed(state.view.sandbox_id)}
                onPay={() => void onPay(state.view)}
              />
            </Device>
            <div className={css.link} aria-hidden="true">
              <span>Voice note</span>
              <ArrowRightIcon />
              <span className={css.linkLine} />
              <ArrowRightIcon />
              <span>Paisa aa gaya</span>
            </div>
            <Device label="Lakshmi" sub="· her phone, live">
              <WorkerPhone sid={state.view.sandbox_id} />
            </Device>
          </div>
          <p className={css.foot}>
            This demo expires in about {Math.max(1, Math.round(state.view.expires_in_s / 60))} minutes.{" "}
            <button type="button" onClick={() => void start(true)} className={css.linkBtn}>
              Start over
            </button>
          </p>
        </>
      ) : null}
    </main>
  );
}
