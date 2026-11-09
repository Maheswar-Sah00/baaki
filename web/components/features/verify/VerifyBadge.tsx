"use client";

// Listen-twice guard (G07). Mount next to a step's audio player:
//   <VerifyBadge messageId={view.messageId} workerLang={lang} />
// Prisma re-hears the generated voice note; the badge says whether the ₹ amounts and the AI label
// were heard. It only warns: sending is never blocked.

import { useCallback, useEffect, useState } from "react";

import { CheckIcon } from "@/components/ui/icons";
import { StatusPill } from "@/components/ui/primitives";
import { inr } from "@/lib/format";
import { runVerify, verifyMessage, VerifyError, type VerifyResult } from "@/lib/features/verify";
import { uiLangOf } from "@/lib/i18n";

import { VERIFY_STRINGS } from "./strings";
import styles from "./verify.module.css";

type State = { kind: "checking" } | { kind: "done"; result: VerifyResult } | { kind: "error"; noAudio: boolean };

const money = (xs: number[]) => xs.map((x) => inr(x)).join(", ");

export function VerifyBadge({ messageId, workerLang }: { messageId: number; workerLang: string | null | undefined }) {
  const s = VERIFY_STRINGS[uiLangOf(workerLang)];
  const [attempt, setAttempt] = useState(0);
  const key = `${messageId}:${attempt}`;
  // The result is tagged with the request it answers; anything older shows as "checking".
  const [settled, setSettled] = useState<{ key: string; state: State } | null>(null);
  const state: State = settled && settled.key === key ? settled.state : { kind: "checking" };

  useEffect(() => {
    const ctrl = new AbortController();
    const job = attempt === 0 ? verifyMessage(messageId, ctrl.signal) : runVerify(messageId, { signal: ctrl.signal });
    job
      .then((result) => setSettled({ key, state: { kind: "done", result } }))
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const noAudio = e instanceof VerifyError && (e.code === "no_audio" || e.code === "audio_missing");
        setSettled({ key, state: { kind: "error", noAudio } });
      });
    return () => ctrl.abort();
  }, [messageId, attempt, key]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  if (state.kind === "checking") {
    return (
      <div className={styles.badge} data-tone="checking" role="status" aria-live="polite">
        <StatusPill tone="live">{s.checking}</StatusPill>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className={styles.badge} data-tone="warn" role="status" aria-live="polite">
        <p className={styles.line}>{state.noAudio ? s.noAudio : s.error}</p>
        {state.noAudio ? null : (
          <button type="button" className="fx-pill-btn" onClick={retry}>
            {s.retry}
          </button>
        )}
      </div>
    );
  }

  const r = state.result;
  const heard = (
    <details className={styles.heard}>
      <summary>{s.heard}</summary>
      <p lang={r.language_code?.startsWith("te") ? "te" : "hi"}>{r.transcript || "—"}</p>
      {r.cached ? null : <p className={styles.meta}>{s.took((r.ms / 1000).toFixed(1))}</p>}
    </details>
  );

  if (r.verified) {
    return (
      <div className={styles.badge} data-tone="ok" role="status" aria-live="polite">
        <p className={styles.title}>
          <CheckIcon className={styles.icon} />
          <span>{r.total_expected != null ? s.ok(inr(r.total_expected)) : s.okNoTotal}</span>
        </p>
        {heard}
      </div>
    );
  }

  return (
    <div className={styles.badge} data-tone="warn" role="alert">
      <p className={styles.title}>
        <span aria-hidden="true" className={styles.bang}>
          !
        </span>
        <span>{s.warnTitle}</span>
      </p>
      <ul className={styles.list}>
        {r.missing.length ? <li>{s.missing(money(r.missing))}</li> : null}
        {r.extra.length ? <li>{s.extra(money(r.extra))}</li> : null}
        {!r.disclosure_heard ? <li>{s.noDisclosure}</li> : null}
      </ul>
      <p className={styles.line}>{s.advice}</p>
      {heard}
    </div>
  );
}

export default VerifyBadge;
