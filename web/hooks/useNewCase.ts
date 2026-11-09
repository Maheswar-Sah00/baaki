"use client";

// Confirm flow, one main action per phase:
//   extracting → home (which home is this?) → review (facts + calculation + read-back, ✓ / ✗) → done
//   1. POST /api/cases/extract           proposed facts (LLM structure, parser amounts) + preview
//   2. POST /api/cases                   a DRAFT case with the chosen home (and her chip edits as facts)
//   3. POST /api/cases/{id}/readback     read-back audio in her language (text works if audio fails)
//   4. POST /api/cases/{id}/confirm      confirmed=false recalculates (Haq Check toggle); true confirms
// Nothing goes to the employer from here; the case screen does that after she confirms.

import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { confirmCase, createCase, errorMessage, extract, getCase, mediaUrl, readback as postReadback } from "@/lib/api";
import { draftStore, type Draft } from "@/lib/store";
import type { CaseDetail, Employer, ExtractResponse, Facts, LangCode, ReadbackAudio, Worker } from "@/lib/types";

export type NewCasePhase = "extracting" | "home" | "creating" | "review" | "saving" | "done" | "rejected" | "error";

export type HomeChoice =
  | { kind: "existing"; employerId: number; name: string }
  | { kind: "new"; name: string; language: LangCode };

/** The employer's likely language: the "other" one for the two-way demo. */
export function defaultEmployerLang(workerLang: string | null | undefined): LangCode {
  return workerLang?.startsWith("te") ? "hi-en" : "te-IN";
}

function langHint(d: Draft): string | null {
  if (d.listenLang === "te" || d.listenLang === "te-IN") return "te";
  if (d.listenLang === "hinglish" || d.listenLang === "hi-en") return "hinglish";
  return d.detectedLang ?? null;
}

/** Her chip edits on the Baaki Meter become fact overrides. */
export function overridesFromDraft(d: Draft): Facts | null {
  const s = d.summary;
  if (!d.chipsEdited || !s) return null;
  const f: Facts = {};
  if (s.monthly_wage != null) f.monthly_wage = s.monthly_wage;
  if (s.months_unpaid != null) {
    f.months_unpaid = s.months_unpaid;
    f.unpaid_months = []; // let the calculator count back from the months she confirmed
    f.unpaid_month_numbers = [];
  }
  f.deductions = s.cuts.map((c) => ({ amount: c.amount, reason: c.reason ?? "other", days_absent: c.days_absent }));
  f.advance_outstanding = s.advance ?? 0;
  return f;
}

function guessHome(name: string | null | undefined, employers: Employer[]): Employer | null {
  if (!name) return null;
  const n = name.toLowerCase().replace(/\s+(ji|garu|madam|sir|saab|sahab)$/i, "").trim();
  return employers.find((e) => e.name.toLowerCase().includes(n) || n.includes(e.name.toLowerCase().split(" ")[0])) ?? null;
}

export function useNewCase(opts: {
  worker: Worker | null;
  employers: Employer[];
  /** Resume an existing draft case (e.g. /case/{id} while it is still a draft). */
  resumeCaseId?: number | null;
  /** Auto-play the read-back when it is ready (needs a prior tap for autoplay on most phones). */
  onReadback?: (r: ReadbackAudio) => void;
}) {
  const { worker, employers, resumeCaseId = null } = opts;
  const [phase, setPhase] = useState<NewCasePhase>(resumeCaseId ? "creating" : "extracting");
  const [draft] = useState<Draft>(() => draftStore.get());
  const [preview, setPreview] = useState<ExtractResponse | null>(null);
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [home, setHome] = useState<HomeChoice | null>(null);
  const [includeShortfall, setIncludeShortfall] = useState(false);
  const [rb, setRb] = useState<ReadbackAudio | null>(null);
  const [rbLoading, setRbLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  const loadReadback = useCallback(async (id: number) => {
    setRbLoading(true);
    try {
      const r = await postReadback(id, { audio: true });
      const fixed = { ...r, audio_url: mediaUrl(r.audio_url) };
      setRb(fixed);
      return fixed;
    } catch {
      return null; // the text read-back is on the case already
    } finally {
      setRbLoading(false);
    }
  }, []);

  const onReadback = useRef(opts.onReadback);
  useEffect(() => {
    onReadback.current = opts.onReadback;
  });

  const toReview = useCallback(
    async (c: CaseDetail) => {
      setCaseData(c);
      setIncludeShortfall(!!c.facts?.include_shortfall);
      setPhase("review");
      const r = await loadReadback(c.id);
      if (r) onReadback.current?.(r);
    },
    [loadReadback],
  );

  // Kick off once: extract (new) or load the draft case (resume).
  const begin = useEffectEvent(async () => {
    try {
      const existing = resumeCaseId ?? draft.caseId;
      if (existing) {
        const c = await getCase(existing);
        if (c.status === "draft") {
          await toReview(c);
          return;
        }
        if (resumeCaseId) {
          setCaseData(c);
          setPhase("done");
          return;
        }
      }
      if (!draft.transcript.trim()) {
        setError("nothing_said");
        setPhase("error");
        return;
      }
      const ex = await extract({
        text: draft.transcript,
        lang: langHint(draft),
        worker_lang: worker?.language ?? null,
        use_llm: true,
      });
      setPreview(ex);
      setPhase("home");
    } catch (err) {
      setError(errorMessage(err));
      setPhase("error");
    }
  });

  useEffect(() => {
    if (started.current) return;
    if (!resumeCaseId && !worker) return; // wait for the worker (language for the read-back)
    started.current = true;
    void Promise.resolve().then(() => begin());
  }, [worker, resumeCaseId]);

  // Preselect the home once facts and the employer list are in.
  const suggested = useMemo(() => guessHome(preview?.facts.employer_name, employers), [preview, employers]);
  const homeChoice: HomeChoice | null = useMemo(
    () =>
      home ??
      (preview
        ? suggested
          ? { kind: "existing", employerId: suggested.id, name: suggested.name }
          : {
              kind: "new",
              name: (preview.facts.employer_name as string | null) ?? "",
              language: defaultEmployerLang(worker?.language),
            }
        : null),
    [home, preview, suggested, worker?.language],
  );

  /** Pick the home and create the draft case. */
  const chooseHome = useCallback(
    async (choice: HomeChoice | null = homeChoice) => {
      if (!choice || !worker || !preview) return null;
      if (choice.kind === "new" && !choice.name.trim()) {
        setError("employer_name_required");
        return null;
      }
      setHome(choice);
      setPhase("creating");
      setError(null);
      try {
        const facts: Facts = { ...preview.facts, ...(overridesFromDraft(draft) ?? {}) };
        delete facts.extraction;
        const c = await createCase({
          worker_id: worker.id,
          employer_id: choice.kind === "existing" ? choice.employerId : null,
          employer: choice.kind === "new" ? { name: choice.name.trim(), language: choice.language } : null,
          transcript: draft.transcript,
          lang: draft.detectedLang ?? langHint(draft),
          facts,
          include_shortfall: false,
          use_llm: false, // the preview already used the LLM; these facts override the parser
        });
        draftStore.set({ caseId: c.id });
        await toReview(c);
        return c;
      } catch (err) {
        setError(errorMessage(err));
        setPhase("home");
        return null;
      }
    },
    [draft, homeChoice, preview, toReview, worker],
  );

  /** Haq Check toggle: recalculates the draft with or without the minimum-wage shortfall. */
  const toggleShortfall = useCallback(
    async (value: boolean) => {
      if (!caseData) return;
      setIncludeShortfall(value);
      try {
        const c = await confirmCase(caseData.id, { confirmed: false, include_shortfall: value });
        setCaseData(c);
      } catch (err) {
        setError(errorMessage(err));
        setIncludeShortfall(!value);
      }
    },
    [caseData],
  );

  /** ✓ Haan: confirm the read-back. Returns the case id to navigate to. */
  const yes = useCallback(async () => {
    if (!caseData) return null;
    setPhase("saving");
    try {
      const c = await confirmCase(caseData.id, { confirmed: true, include_shortfall: includeShortfall });
      setCaseData(c);
      draftStore.clear();
      setPhase("done");
      return c.id;
    } catch (err) {
      setError(errorMessage(err));
      setPhase("review");
      return null;
    }
  }, [caseData, includeShortfall]);

  /** ✗ Nahi: go back and say it again (the draft case stays a draft and is not sent anywhere). */
  const no = useCallback(() => {
    draftStore.set({ caseId: null });
    setPhase("rejected");
  }, []);

  const calc = caseData?.calc ?? preview?.calc ?? null;
  const haq = calc?.haq_check ?? null;
  return {
    phase,
    draft,
    preview,
    facts: caseData?.facts ?? preview?.facts ?? null,
    calc,
    caseData,
    /** Read-back in her language: text always, audio when Timbre worked. */
    readbackText: rb?.plain ?? caseData?.readback.plain ?? preview?.readback.plain ?? "",
    readbackSentences: rb?.sentences ?? caseData?.readback.sentences ?? preview?.readback.sentences ?? [],
    readbackAudioUrl: rb?.audio_url ?? null,
    readbackAudioFailed: !!rb?.tts_error,
    readbackLoading: rbLoading,
    replayReadback: useCallback(async () => (caseData ? loadReadback(caseData.id) : null), [caseData, loadReadback]),
    homeChoice,
    suggestedHome: suggested,
    setHome,
    chooseHome,
    includeShortfall,
    toggleShortfall,
    haq,
    hasShortfall: (calc?.min_wage_shortfall ?? 0) > 0,
    shortfallTotal: calc?.min_wage_shortfall ?? 0,
    total: caseData ? caseData.total_due : calc ? (includeShortfall ? calc.total_with_shortfall : calc.total) : 0,
    warnings: preview?.warnings ?? caseData?.facts?.extraction?.warnings ?? [],
    yes,
    no,
    error,
  };
}
