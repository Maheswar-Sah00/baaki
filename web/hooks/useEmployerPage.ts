"use client";

// The employer's public page (/e/{token}): no login, in the employer's language.
//   play()      plays the voice note and POSTs /played once
//   pay()       "I've paid" → POST /pay. This is a CLAIM: nothing changes until the worker confirms the money
//               arrived; while `pendingConfirmation` is true the page polls every 5 s, so the badge appears by itself
//   reload()    refetch now (call it right after pay())
//   plan(n)     pay in 2 or 3 parts → POST /plan
//   reply       record → POST /reply (STT + translation + TTS for the worker); reply.sendText(t) types instead
// `upi.qr` is a QR data URL for desktops (generated client-side); phones use `upi.link`.

import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { employerReply, errorMessage, getEmployerPage, markPlayed, mediaUrl, pay as postPay, planInstalments } from "@/lib/api";
import { useRecorder } from "@/lib/recorder";
import { isLikelyMobile } from "@/lib/share";
import type { PayResponse, PlanResponse, ReplyResponse } from "@/lib/types";
import { useAudioPlayer } from "./useAudioPlayer";
import { useHydrated } from "./useSettings";
import { useResource } from "./useResource";

const CLAIM_POLL_MS = 5000;

export function useEmployerPage(token: string | null, opts: { pollMs?: number | null } = {}) {
  // Poll while his "I've paid" claim waits for her answer (set from the last page we loaded).
  const [awaitingHer, setAwaitingHer] = useState(false);
  const res = useResource(
    token === null ? null : `emp:${token}`,
    (signal) =>
      getEmployerPage(token!, signal).then((p) => {
        setAwaitingHer(!!p.pending_confirmation);
        return p;
      }),
    { pollMs: opts.pollMs ?? (awaitingHer ? CLAIM_POLL_MS : null) },
  );
  const page = res.data;
  const pendingConfirmation = !!page?.pending_confirmation;
  const player = useAudioPlayer();
  const playedSent = useRef(false);
  const hydrated = useHydrated();

  const audioUrl = mediaUrl(page?.audio_url);
  const play = useCallback(async () => {
    if (!audioUrl || !token) return false;
    const ok = await player.toggle(audioUrl);
    if (ok && !playedSent.current) {
      playedSent.current = true;
      markPlayed(token).catch(() => undefined);
    }
    return ok;
  }, [audioUrl, player, token]);

  // ---- pay
  const [paying, setPaying] = useState(false);
  const [payResult, setPayResult] = useState<PayResponse | null>(null);
  const [payError, setPayError] = useState<string | null>(null);
  const pay = useCallback(
    async (amount?: number) => {
      if (!token) return null;
      setPaying(true);
      setPayError(null);
      try {
        const r = await postPay(token, { amount, method: "upi" });
        setPayResult(r);
        if (r.pending_confirmation) setAwaitingHer(true);
        res.refresh();
        return r;
      } catch (err) {
        setPayError(errorMessage(err));
        return null;
      } finally {
        setPaying(false);
      }
    },
    [res, token],
  );

  // ---- plan
  const [planning, setPlanning] = useState(false);
  const [planResult, setPlanResult] = useState<PlanResponse | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const plan = useCallback(
    async (instalments: 2 | 3) => {
      if (!token) return null;
      setPlanning(true);
      setPlanError(null);
      try {
        const r = await planInstalments(token, { instalments });
        setPlanResult(r);
        res.refresh();
        return r;
      } catch (err) {
        setPlanError(errorMessage(err));
        return null;
      } finally {
        setPlanning(false);
      }
    },
    [res, token],
  );

  // ---- voice reply
  const [replying, setReplying] = useState(false);
  const [replyResult, setReplyResult] = useState<ReplyResponse | null>(null);
  const [replyError, setReplyError] = useState<string | null>(null);
  const recorder = useRecorder({
    maxMs: 60_000,
    onRecorded: async (r) => {
      if (!token) return;
      setReplying(true);
      setReplyError(null);
      try {
        const out = await employerReply(token, r.blob, { filename: r.filename, lang: page?.employer.language ?? null });
        setReplyResult(out);
        res.refresh();
      } catch (err) {
        setReplyError(errorMessage(err));
      } finally {
        setReplying(false);
      }
    },
  });

  const employerLang = page?.employer.language ?? null;
  const sendText = useCallback(
    async (text: string) => {
      if (!token || !text.trim()) return null;
      setReplying(true);
      setReplyError(null);
      try {
        const out = await employerReply(token, null, { text, lang: employerLang });
        setReplyResult(out);
        res.refresh();
        return out;
      } catch (err) {
        setReplyError(errorMessage(err));
        return null;
      } finally {
        setReplying(false);
      }
    },
    [employerLang, res, token],
  );

  // ---- UPI: deep link on phones, QR on desktops
  const upiLink = page?.upi?.link ?? null;
  const [qr, setQr] = useState<{ link: string; dataUrl: string } | null>(null);
  useEffect(() => {
    if (!upiLink) return;
    let alive = true;
    QRCode.toDataURL(upiLink, { margin: 1, width: 240, errorCorrectionLevel: "M" })
      .then((dataUrl) => {
        if (alive) setQr({ link: upiLink, dataUrl });
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [upiLink]);

  const fullyPaid = !!page && page.total_due > 0 && page.balance <= 0.5;
  return {
    page,
    loading: res.loading,
    error: res.error ? errorMessage(res.error) : null,
    notFound: !!res.error && (res.error as { status?: number }).status === 404,
    refresh: res.refresh,
    reload: res.refresh,
    lang: page?.employer.language ?? "hi-en",
    audioUrl,
    pdfUrl: mediaUrl(page?.pdf_url),
    player,
    play,
    upi: page?.upi
      ? {
          vpa: page.upi.vpa,
          link: page.upi.link,
          amount: page.balance,
          qr: qr && qr.link === upiLink ? qr.dataUrl : null,
          /** Show the deep link button (phones) or the QR + UPI ID (desktops). Null before hydration. */
          mobile: hydrated ? isLikelyMobile() : null,
        }
      : null,
    fullyPaid,
    /** His claim waits for her: show the waiting panel instead of "I've paid". */
    pendingConfirmation: pendingConfirmation || (!!payResult?.pending_confirmation && !page?.badge && !fullyPaid),
    pendingClaim: page?.pending_claim ?? payResult?.claim ?? null,
    claims: page?.claims ?? [],
    stale: !!page?.stale,
    staleNote: page?.stale_note ?? null,
    overpaid: page?.overpaid ?? 0,
    badge: payResult?.badge ?? page?.badge ?? null,
    pay,
    paying,
    payResult,
    payError,
    plan,
    planning,
    planResult,
    planError,
    planRows: page?.plan ?? [],
    reply: {
      recorder,
      sending: replying,
      result: replyResult,
      error: replyError ?? recorder.error,
      toggle: recorder.toggle,
      /** Typed reply (no mic / voice service down). */
      sendText,
    },
    replies: page?.replies ?? [],
  };
}
