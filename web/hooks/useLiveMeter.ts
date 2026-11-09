"use client";

// The Baaki Meter: an animated rupee counter that ticks through the meter's `steps` with eased
// counting (₹4,000 → ₹8,000 → ₹12,000 → ₹13,000), plus amount chips the worker can remove or fix.
//   load(meterResponse)   from /listen (or any meter result): animates from the current value
//   fromText(text, lang)  typed fallback: debounced POST /api/cases/meter (no LLM, no Gnani)
//   removeChip / editChip re-totals the edited chips with POST /api/cases/meter {chips}
// Read `display` for the number on screen, `tick` (increments at each step) to pulse the UI.

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, isAbort, meter as postMeter } from "@/lib/api";
import { createCounter } from "@/lib/counter";
import type { MeterChip, MeterResponse, MeterSummary, Safety } from "@/lib/types";

function summaryOf(m: MeterResponse): MeterSummary {
  return {
    total: m.total,
    steps: m.steps,
    formula: m.formula,
    monthly_wage: m.monthly_wage,
    months_unpaid: m.months_unpaid,
    cuts: m.cuts,
    advance: m.advance,
    paid: m.paid,
    stated_total: m.stated_total,
    matches_stated_total: m.matches_stated_total,
    days: m.days,
    hours_per_day: m.hours_per_day,
  };
}

export function useLiveMeter(opts: { debounceMs?: number } = {}) {
  const debounceMs = opts.debounceMs ?? 300;
  const [chips, setChips] = useState<MeterChip[]>([]);
  const [summary, setSummary] = useState<MeterSummary | null>(null);
  const [text, setText] = useState("");
  const [lang, setLang] = useState<string | null>(null);
  const [display, setDisplay] = useState(0);
  const [tick, setTick] = useState(0);
  const [animating, setAnimating] = useState(false);
  const [edited, setEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [safety, setSafety] = useState<Safety | null>(null);

  const [counter] = useState(() =>
    createCounter({
      onFrame: setDisplay,
      onStep: () => setTick((t) => t + 1),
      onIdle: () => setAnimating(false),
      onBusy: () => setAnimating(true),
    }),
  );
  const debounceRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      counter.dispose();
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
  }, [counter]);

  const apply = useCallback(
    (m: MeterResponse) => {
      setChips(m.chips ?? []);
      setSummary(summaryOf(m));
      if (m.safety) setSafety(m.safety);
      setEdited(false);
      setError(null);
      counter.animateTo(m.steps ?? [], m.total ?? 0);
    },
    [counter],
  );

  /** Show a meter result (from /listen, /meter or /extract). */
  const load = useCallback(
    (m: MeterResponse, o: { text?: string; lang?: string | null } = {}) => {
      setText(o.text ?? m.text ?? "");
      if (o.lang !== undefined) setLang(o.lang);
      apply(m);
    },
    [apply],
  );

  const request = useCallback(async (body: { text: string; lang: string | null; chips?: MeterChip[] }) => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setBusy(true);
    try {
      return await postMeter(body, ac.signal);
    } catch (err) {
      if (!isAbort(err)) setError(errorMessage(err));
      return null;
    } finally {
      if (abortRef.current === ac) setBusy(false);
    }
  }, []);

  /** Typed fallback: re-meter the text after a short pause in typing. */
  const fromText = useCallback(
    (value: string, l: string | null = lang) => {
      setText(value);
      setLang(l);
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current);
      debounceRef.current = window.setTimeout(async () => {
        if (!value.trim()) {
          setChips([]);
          setSummary(null);
          counter.animateTo([], 0);
          return;
        }
        const m = await request({ text: value, lang: l });
        if (m) apply(m);
      }, debounceMs);
    },
    [apply, counter, debounceMs, lang, request],
  );

  const retotal = useCallback(
    async (next: MeterChip[]) => {
      setChips(next);
      setEdited(true);
      const m = await request({ text, lang, chips: next });
      if (m) {
        setSummary(summaryOf(m));
        counter.animateTo([], m.total ?? 0);
      }
    },
    [counter, lang, request, text],
  );

  const removeChip = useCallback((id: string) => retotal(chips.filter((c) => c.id !== id)), [chips, retotal]);

  const editChip = useCallback(
    (id: string, value: number) => retotal(chips.map((c) => (c.id === id ? { ...c, value } : c))),
    [chips, retotal],
  );

  const reset = useCallback(() => {
    counter.jump(0);
    setChips([]);
    setSummary(null);
    setText("");
    setEdited(false);
    setError(null);
    setSafety(null);
  }, [counter]);

  return {
    /** The animated number to show (rupees, may be fractional mid-animation). */
    display,
    /** Final total after all steps. */
    total: summary?.total ?? 0,
    steps: summary?.steps ?? [],
    formula: summary?.formula ?? "",
    summary,
    chips,
    /** Money chips (amounts) vs. count chips (months / days / hours). */
    amountChips: chips.filter((c) => !c.is_count),
    countChips: chips.filter((c) => c.is_count),
    text,
    lang,
    tick,
    animating,
    edited,
    busy,
    error,
    safety,
    load,
    fromText,
    removeChip,
    editChip,
    reset,
  };
}

export type LiveMeter = ReturnType<typeof useLiveMeter>;
