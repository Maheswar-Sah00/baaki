"use client";

// One case: GET /api/cases/{id}, polled every ~3 s so the worker sees the payment land.
// When a new "paid_alert" message (or a higher amount_paid) shows up after the first load, `celebration`
// is set: show "Paisa aa gaya!" and play `celebration.audioUrl` (the <excited> alert in her language).
// The last paid_alert she has seen is remembered per case in localStorage, so an alert that landed while the
// screen was closed is celebrated the next time she opens the case (once), not only live changes.

import { useCallback, useEffect, useRef, useState } from "react";
import { confirmCase, errorMessage, getCase, legalPackUrl, mediaKeyUrl, readback } from "@/lib/api";
import type { CaseDetail, Facts, MessageRow, ReadbackAudio } from "@/lib/types";
import { useResource } from "./useResource";

export type Celebration = {
  messageId: number | null;
  text: string;
  audioUrl: string | null;
  amountPaid: number;
  balance: number;
  fullyPaid: boolean;
};

function latestAlert(c: CaseDetail): MessageRow | null {
  const alerts = c.messages.filter((m) => m.step === "paid_alert" && m.direction === "to_worker");
  return alerts.length ? alerts[alerts.length - 1] : null;
}

const SEEN_KEY = (caseId: number) => `baaki.paidSeen.${caseId}`;
/** An alert older than this is history, not news: opening an old paid case on a new phone stays quiet. */
const MISSED_ALERT_MAX_AGE_MS = 14 * 24 * 3600 * 1000;

function readSeen(caseId: number): number | null {
  try {
    const v = window.localStorage.getItem(SEEN_KEY(caseId));
    return v === null ? null : Number(v) || 0;
  } catch {
    return null;
  }
}

function writeSeen(caseId: number, alertId: number) {
  try {
    window.localStorage.setItem(SEEN_KEY(caseId), String(alertId));
  } catch {
    /* private mode: the live check still works */
  }
}

function isRecent(iso: string | null | undefined): boolean {
  const t = iso ? Date.parse(iso) : NaN;
  return Number.isFinite(t) && Date.now() - t <= MISSED_ALERT_MAX_AGE_MS;
}

export function useCase(caseId: number | null, opts: { pollMs?: number | null; onPaid?: (c: Celebration) => void } = {}) {
  const pollMs = opts.pollMs === undefined ? 3000 : opts.pollMs;
  const res = useResource(caseId === null ? null : `case:${caseId}`, (signal) => getCase(caseId!, signal), { pollMs });
  const [celebration, setCelebration] = useState<Celebration | null>(null);
  const seen = useRef<{ caseId: number; alertId: number; paid: number } | null>(null);
  const onPaid = useRef(opts.onPaid);

  useEffect(() => {
    onPaid.current = opts.onPaid;
  }, [opts.onPaid]);

  // Detect a payment that landed after the screen opened.
  const data = res.data;
  useEffect(() => {
    if (!data) return;
    const alert = latestAlert(data);
    const alertId = alert?.id ?? 0;
    const prev = seen.current;
    seen.current = { caseId: data.id, alertId, paid: data.amount_paid };
    const stored = readSeen(data.id);
    if (alertId > (stored ?? 0)) writeSeen(data.id, alertId);
    let fire: boolean;
    if (!prev || prev.caseId !== data.id) {
      // first load: celebrate an alert she has not seen yet (it landed while the screen was closed)
      fire = alert !== null && alertId > (stored ?? 0) && isRecent(alert.sent_at ?? alert.created_at);
    } else {
      fire = alertId > prev.alertId || data.amount_paid > prev.paid + 0.5;
    }
    if (fire) {
      const c: Celebration = {
        messageId: alert?.id ?? null,
        text: alert?.text ?? "",
        audioUrl: mediaKeyUrl(alert?.audio_path),
        amountPaid: data.amount_paid,
        balance: data.balance,
        fullyPaid: data.balance <= 0.5,
      };
      // Defer to keep state updates out of the effect body.
      queueMicrotask(() => {
        setCelebration(c);
        onPaid.current?.(c);
      });
    }
  }, [data]);

  const [rb, setRb] = useState<ReadbackAudio | null>(null);
  const [rbLoading, setRbLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  /** Read-back text + audio for this case (one cached Timbre call). */
  const loadReadback = useCallback(
    async (withAudio = true) => {
      if (caseId === null) return null;
      setRbLoading(true);
      try {
        const r = await readback(caseId, { audio: withAudio });
        setRb(r);
        return r;
      } catch (err) {
        setActionError(errorMessage(err));
        return null;
      } finally {
        setRbLoading(false);
      }
    },
    [caseId],
  );

  /** POST /confirm. confirmed=false just recalculates (Haq Check toggle, edited facts). */
  const confirm = useCallback(
    async (body: { confirmed?: boolean; facts?: Facts | null; include_shortfall?: boolean | null }) => {
      if (caseId === null) return null;
      try {
        const c = await confirmCase(caseId, body);
        res.setData(c);
        return c;
      } catch (err) {
        setActionError(errorMessage(err));
        return null;
      }
    },
    [caseId, res],
  );

  const c = data;
  const replies = c ? c.messages.filter((m) => m.step === "reply" && m.direction === "to_worker") : [];
  const plan = c ? c.payments.filter((p) => p.instalment_no) : [];
  const paid = c ? c.payments.filter((p) => p.status === "paid") : [];
  return {
    caseData: c,
    loading: res.loading,
    error: res.error ? errorMessage(res.error) : null,
    notFound: !!res.error && (res.error as { status?: number }).status === 404,
    refresh: res.refresh,
    setCase: res.setData,
    isDraft: c ? c.status === "draft" : false,
    isPaid: c ? c.status === "paid" || (c.total_due > 0 && c.balance <= 0.5) : false,
    replies,
    plan,
    payments: paid,
    legalPackUrl: caseId === null ? null : legalPackUrl(caseId),
    employerPath: c?.employer_path ?? null,
    celebration,
    dismissCelebration: useCallback(() => setCelebration(null), []),
    readback: rb,
    readbackLoading: rbLoading,
    loadReadback,
    confirm,
    actionError,
  };
}
