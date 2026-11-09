"use client";

// The Polite → Firm → Formal ladder for one case.
//   generate(step)  POST /api/cases/{id}/messages/{step}: text in the employer's language, the
//                   worker's-language version, a voice note (AI disclosure first) and the PDF
//   share(step)     Web Share with the voice-note file + text + employer link → WhatsApp URL → copy,
//                   then POST /api/messages/{id}/sent (she presses Send herself every time)
// Messages already on the case (from GET /api/cases/{id}) show up before anything is generated.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { employerLink, errorMessage, makeStep, markSent, mediaKeyUrl, mediaUrl } from "@/lib/api";
import { fileFromUrl, shareMessage, type ShareResult } from "@/lib/share";
import type { CaseDetail, LadderStep, StepOptions, StepResponse } from "@/lib/types";

export const LADDER: LadderStep[] = ["polite", "firm", "formal"];

/** What a screen needs to show one step, whether it was just generated or loaded with the case. */
export type StepView = {
  step: LadderStep;
  messageId: number;
  text: string;
  textWorkerLang: string | null;
  language: string;
  audioUrl: string | null;
  pdfUrl: string | null;
  status: string; // draft | sent | played | replied
  sentAt: string | null;
  createdAt: string;
  voiceMode: "clone" | "stock" | null;
  audioError: string | null;
  upiLink: string | null;
  disclosure: string | null;
  replyBy: string | null;
};

type StepState = {
  generating: boolean;
  error: string | null;
  generated: StepResponse | null;
  sharing: boolean;
  shareResult: ShareResult | null;
};

const EMPTY: StepState = { generating: false, error: null, generated: null, sharing: false, shareResult: null };

function fromGenerated(r: StepResponse, step: LadderStep): StepView {
  const audioErr = r.audio_error ? (r.audio_error.message as string | undefined) ?? "voice note failed" : null;
  return {
    step,
    messageId: r.message_id,
    text: r.text,
    textWorkerLang: r.text_worker_lang,
    language: r.language,
    audioUrl: mediaUrl(r.audio_url),
    pdfUrl: mediaUrl(r.pdf_url),
    status: r.status,
    sentAt: r.sent_at,
    createdAt: r.created_at,
    voiceMode: r.voice_mode ?? null,
    audioError: audioErr,
    upiLink: r.upi_link,
    disclosure: r.disclosure ?? null,
    replyBy: r.reply_by ?? null,
  };
}

export function useMessages(
  caseId: number | null,
  caseData: CaseDetail | null,
  opts: { onChanged?: () => void; defaults?: StepOptions } = {},
) {
  const [steps, setSteps] = useState<Record<LadderStep, StepState>>({ polite: EMPTY, firm: EMPTY, formal: EMPTY });
  const onChanged = useRef(opts.onChanged);
  useEffect(() => {
    onChanged.current = opts.onChanged;
  }, [opts.onChanged]);

  const patch = useCallback(
    (step: LadderStep, p: Partial<StepState>) => setSteps((s) => ({ ...s, [step]: { ...s[step], ...p } })),
    [],
  );

  // Latest stored message per step (from the case), overridden by what was generated in this session.
  const views = useMemo(() => {
    const out: Record<LadderStep, StepView | null> = { polite: null, firm: null, formal: null };
    for (const m of caseData?.messages ?? []) {
      if (m.direction !== "to_employer" || !LADDER.includes(m.step as LadderStep)) continue;
      const step = m.step as LadderStep;
      out[step] = {
        step,
        messageId: m.id,
        text: m.text,
        textWorkerLang: m.text_worker_lang,
        language: m.language,
        audioUrl: mediaKeyUrl(m.audio_path),
        pdfUrl: mediaKeyUrl(m.pdf_path),
        status: m.status,
        sentAt: m.sent_at,
        createdAt: m.created_at,
        voiceMode: null,
        audioError: null,
        upiLink: null,
        disclosure: null,
        replyBy: null,
      };
    }
    for (const step of LADDER) {
      const g = steps[step].generated;
      if (g) {
        const stored = out[step];
        const v = fromGenerated(g, step);
        // keep the stored status if it moved on (sent / played / replied) since we generated it
        if (stored && stored.messageId === v.messageId) {
          v.status = stored.status;
          v.sentAt = stored.sentAt;
        }
        if (!stored || stored.messageId <= v.messageId) out[step] = v;
      }
    }
    return out;
  }, [caseData, steps]);

  const isSent = (v: StepView | null) => !!v && ["sent", "played", "replied"].includes(v.status);

  /** The step to suggest next: the first one not sent yet. */
  const nextStep: LadderStep | null = LADDER.find((s) => !isSent(views[s])) ?? null;

  // Voice-note Files ready for Web Share, keyed by audio URL. Prepared ahead of the tap because
  // navigator.share() must run while the tap's user activation is still fresh.
  const files = useRef(new Map<string, File>());
  const prepareFile = useCallback(async (step: LadderStep, audioUrl: string | null) => {
    if (!audioUrl || files.current.has(audioUrl)) return;
    try {
      files.current.set(audioUrl, await fileFromUrl(audioUrl, `baaki-${step}.ogg`));
    } catch {
      /* sharing still works with text + link */
    }
  }, []);

  const generate = useCallback(
    async (step: LadderStep, o: StepOptions = {}) => {
      if (caseId === null) return null;
      patch(step, { generating: true, error: null, shareResult: null });
      try {
        const r = await makeStep(caseId, step, {
          use_llm: true,
          audio: true,
          pdf: true,
          voice: "auto",
          ...opts.defaults,
          ...o,
        });
        patch(step, { generating: false, generated: r });
        void prepareFile(step, mediaUrl(r.audio_url));
        onChanged.current?.();
        return r;
      } catch (err) {
        patch(step, { generating: false, error: errorMessage(err) });
        return null;
      }
    },
    [caseId, opts.defaults, patch, prepareFile],
  );

  // Stored messages (from the case) get their audio file prepared too, so Share has it ready.
  useEffect(() => {
    for (const step of LADDER) void prepareFile(step, views[step]?.audioUrl ?? null);
  }, [views, prepareFile]);

  /** Share from a tap. Marks the message sent unless she cancelled. */
  const share = useCallback(
    async (step: LadderStep): Promise<ShareResult | null> => {
      const v = views[step];
      if (!v || !caseData) return null;
      patch(step, { sharing: true });
      const link = employerLink(caseData.employer_path);
      const result = await shareMessage({
        text: v.text,
        url: link,
        title: "Baaki",
        file: v.audioUrl ? files.current.get(v.audioUrl) ?? null : null,
      });
      patch(step, { sharing: false, shareResult: result });
      if (result !== "cancelled" && result !== "failed") {
        try {
          await markSent(v.messageId);
          onChanged.current?.();
        } catch (err) {
          patch(step, { error: errorMessage(err) });
        }
      }
      return result;
    },
    [caseData, patch, views],
  );

  return {
    steps: LADDER,
    views,
    state: steps,
    nextStep,
    isSent,
    generate,
    share,
    employerUrl: caseData ? employerLink(caseData.employer_path) : null,
  };
}
