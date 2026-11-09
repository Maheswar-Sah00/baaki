"use client";

// Opt-in voice profile: consent first (plain words), record 10–20 s, POST with consent=true.
// Only the embedding is stored, never the audio. Delete removes it and every clip in that voice.

import { useCallback, useState } from "react";
import { createVoiceProfile, deleteVoiceProfile, errorMessage, getVoiceProfile } from "@/lib/api";
import { useRecorder } from "@/lib/recorder";
import { useResource } from "./useResource";

export const VOICE_MIN_MS = 10_000;
export const VOICE_MAX_MS = 20_000;

export function useVoiceProfile(workerId: number | null) {
  const res = useResource(workerId === null ? null : `voice:${workerId}`, (signal) => getVoiceProfile(workerId!, signal));
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justDeleted, setJustDeleted] = useState(false);

  const recorder = useRecorder({
    maxMs: VOICE_MAX_MS,
    minMs: VOICE_MIN_MS,
    onRecorded: async (r) => {
      if (workerId === null) return;
      setSaving(true);
      setError(null);
      try {
        const p = await createVoiceProfile(workerId, r.blob, consent);
        res.setData(p);
        setJustDeleted(false);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setSaving(false);
      }
    },
  });

  const remove = useCallback(async () => {
    if (workerId === null) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteVoiceProfile(workerId);
      setJustDeleted(true);
      res.refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  }, [res, workerId]);

  const profile = res.data;
  return {
    profile,
    exists: !!profile?.exists,
    /** Consent wording from the backend in the worker's language. */
    consentText: profile?.consent_text ?? null,
    loading: res.loading,
    error: error ?? recorder.error ?? (res.error ? errorMessage(res.error) : null),
    consent,
    setConsent,
    recorder,
    /** 0..1 of the 20 s window, for a progress ring. */
    progress: Math.min(1, recorder.elapsedMs / VOICE_MAX_MS),
    longEnough: recorder.elapsedMs >= VOICE_MIN_MS,
    /** Start/stop recording; recording only starts after consent. */
    toggle: useCallback(() => {
      if (!consent && recorder.state === "idle") {
        setError("consent_required");
        return;
      }
      recorder.toggle();
    }, [consent, recorder]),
    saving,
    remove,
    deleting,
    justDeleted,
  };
}
