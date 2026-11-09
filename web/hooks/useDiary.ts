"use client";

// The 5-second Kaam Diary: a one-tap or spoken check-in, timestamped and SHA-256 hash-chained by the
// backend. `chain.valid` is the "untouched record" badge.
// A voice check-in without text spends one Gnani STT call; the quick tap check-in spends none.

import { useCallback, useState } from "react";
import { addDiary, errorMessage, listDiary } from "@/lib/api";
import { useRecorder } from "@/lib/recorder";
import type { DiaryAdded, DiaryKind, ListenLang } from "@/lib/types";
import { useResource } from "./useResource";

export function useDiary(workerId: number | null, opts: { employerId?: number | null; lang?: ListenLang } = {}) {
  const employerId = opts.employerId ?? null;
  const res = useResource(
    workerId === null ? null : `diary:${workerId}:${employerId ?? "all"}`,
    (signal) => listDiary(workerId!, employerId, signal),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<DiaryAdded | null>(null);

  const add = useCallback(
    async (body: { text?: string; employerId?: number | null; caseId?: number | null; kind?: DiaryKind; audio?: Blob | null }) => {
      if (workerId === null) return null;
      setSaving(true);
      setError(null);
      try {
        const r = await addDiary({ workerId, lang: opts.lang ?? "auto", ...body });
        setLast(r);
        res.refresh();
        return r;
      } catch (err) {
        setError(errorMessage(err));
        return null;
      } finally {
        setSaving(false);
      }
    },
    [opts.lang, res, workerId],
  );

  /** One tap: "worked today at {home}" (text only, no Gnani). */
  const quickCheckin = useCallback(
    (employer: { id: number; name: string }, caseId?: number | null, hours?: number | null) =>
      add({
        text: hours ? `Worked today at ${employer.name}, ${hours} hours` : `Worked today at ${employer.name}`,
        employerId: employer.id,
        caseId: caseId ?? null,
        kind: "checkin",
      }),
    [add],
  );

  const recorder = useRecorder({
    maxMs: 15_000,
    onRecorded: (r) => void add({ audio: r.blob, kind: "checkin" }),
  });

  const entries = res.data?.entries ?? [];
  return {
    entries: [...entries].reverse(), // newest first
    chain: res.data?.chain ?? null,
    loading: res.loading,
    error: error ?? recorder.error ?? (res.error ? errorMessage(res.error) : null),
    saving,
    last,
    add,
    quickCheckin,
    recorder,
    refresh: res.refresh,
  };
}
