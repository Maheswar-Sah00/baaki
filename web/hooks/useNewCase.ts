"use client";

// Confirm flow, one main action per phase:
//   extracting → home (which home is this?) → review (facts + calculation + read-back, ✓ / ✗) → done
//   1. POST /api/cases/extract           proposed facts (LLM structure, parser amounts) + preview
//   2. POST /api/cases                   a DRAFT case with the chosen home (and her chip edits as facts);
//                                        a home with an open case gets THAT case recomputed (`updated: true`),
//                                        so re-telling the story never makes a second Sharma ji card
//   3. POST /api/cases/{id}/readback     read-back audio in her language (text works if audio fails)
//   4. POST /api/cases/{id}/confirm      confirmed=false recalculates (Haq Check toggle); true confirms
// Nothing goes to the employer from here; the case screen does that after she confirms.
// Home picker: GET /api/workers/{id}/match-home matches a name in any script (శర్మ గారు = Sharma ji) with
// the LLM off; the local guess is the fallback. No worker yet (empty database): phase "error", noWorker.

import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import {
  ApiError,
  confirmCase,
  createCase,
  errorMessage,
  extract,
  getCase,
  getDashboard,
  mediaUrl,
  readback as postReadback,
} from "@/lib/api";
import { draftStore, settingsStore, type Draft } from "@/lib/store";
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
  if (!n) return null;
  return employers.find((e) => e.name.toLowerCase().includes(n) || n.includes(e.name.toLowerCase().split(" ")[0])) ?? null;
}

/** Backend home match (any script, no LLM). null when unsure or unreachable: the local guess stays. */
async function matchHome(workerId: number, name: string, signal?: AbortSignal): Promise<Employer | null> {
  try {
    const res = await fetch(`/api/workers/${workerId}/match-home?name=${encodeURIComponent(name)}`, {
      cache: "no-store",
      signal,
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { match: Employer | null };
    return body.match ?? null;
  } catch {
    return null;
  }
}

/** "Nahi" after a re-telling: put the open case back as she had confirmed it. */
async function undoRetell(caseId: number): Promise<void> {
  try {
    await fetch(`/api/cases/${caseId}/undo-retell`, { method: "POST", cache: "no-store" });
  } catch {
    /* the case keeps the new telling; she can tell it again */
  }
}

/** The dashboard says this worker does not exist (empty database, or a stale remembered id). */
export function isNoWorker(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404 && (err.code === "no_worker" || /worker not found/i.test(err.message));
}

export const NO_WORKER_MESSAGE = "No worker profile on this server yet. Go back home and start fresh (or reset the demo).";

type CaseWithUpdate = CaseDetail & { updated?: boolean; previous_total?: number };

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
  const [noWorker, setNoWorker] = useState(false);
  const [serverHome, setServerHome] = useState<Employer | null>(null);
  /** This telling updated a home's open case (instead of making a second one). */
  const [retold, setRetold] = useState<{ caseId: number; previousTotal: number | null } | null>(null);
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
        // a draft, or an open case whose re-telling she has not confirmed yet: back to the review
        if (c.status === "draft" || (!c.readback_confirmed && !resumeCaseId)) {
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

  // No worker to wait for? Ask the dashboard ourselves, so an empty database shows an error, not a spinner.
  const probeWorker = useEffectEvent(async (signal: AbortSignal) => {
    try {
      await getDashboard(settingsStore.get().workerId, signal);
    } catch (err) {
      if (signal.aborted) return;
      if (isNoWorker(err)) {
        setNoWorker(true);
        setError(NO_WORKER_MESSAGE);
      } else {
        setError(errorMessage(err));
      }
      setPhase("error");
    }
  });
  useEffect(() => {
    if (resumeCaseId || worker) return;
    const ctl = new AbortController();
    const t = setTimeout(() => void probeWorker(ctl.signal), 1500); // the screen's own dashboard load usually wins
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [worker, resumeCaseId]);

  // Backend home match (Telugu / Devanagari / Latin names, LLM off).
  const spokenName = (preview?.facts.employer_name as string | null | undefined) ?? null;
  useEffect(() => {
    if (!worker || !spokenName) return;
    const ctl = new AbortController();
    void matchHome(worker.id, spokenName, ctl.signal).then((m) => {
      if (!ctl.signal.aborted) setServerHome(m);
    });
    return () => ctl.abort();
  }, [worker, spokenName]);

  // Preselect the home once facts and the employer list are in (backend match first, local guess second).
  const suggested = useMemo(() => {
    if (serverHome) return employers.find((e) => e.id === serverHome.id) ?? serverHome;
    return guessHome(spokenName, employers);
  }, [serverHome, spokenName, employers]);
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
        const c: CaseWithUpdate = await createCase({
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
        setRetold(c.updated ? { caseId: c.id, previousTotal: c.previous_total ?? null } : null);
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

  /** ✗ Nahi: go back and say it again (the draft case stays a draft and is not sent anywhere; a re-telling of
   *  an open case is undone, so the case keeps what she confirmed before). */
  const no = useCallback(() => {
    draftStore.set({ caseId: null });
    if (retold) void undoRetell(retold.caseId);
    setRetold(null);
    setPhase("rejected");
  }, [retold]);

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
    /** Empty database / unknown worker: show "start fresh" instead of the spoken-story flow. */
    noWorker,
    /** This telling updated the home's open case: show "Updated your Sharma ji case (was ₹X)". */
    retold,
  };
}
