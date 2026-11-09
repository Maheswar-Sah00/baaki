"use client";

// Worker home: one card per employer from GET /api/workers/{id}/dashboard, totals, and the demo reset.

import { useCallback, useState } from "react";
import { errorMessage, getDashboard, resetDemo } from "@/lib/api";
import { draftStore, safetyStore } from "@/lib/store";
import type { DemoReset } from "@/lib/types";
import { useResource } from "./useResource";

export function useDashboard(workerId: number | null, opts: { pollMs?: number | null } = {}) {
  const res = useResource(workerId === null ? null : `dash:${workerId}`, (signal) => getDashboard(workerId!, signal), {
    pollMs: opts.pollMs ?? null,
  });
  const [resetting, setResetting] = useState(false);
  const [resetResult, setResetResult] = useState<DemoReset | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);

  /** POST /api/demo/reset, clear this tab's draft, reload the cards. */
  const reset = useCallback(async () => {
    setResetting(true);
    setResetError(null);
    try {
      const r = await resetDemo();
      draftStore.clear();
      safetyStore.clear();
      setResetResult(r);
      res.refresh();
      return r;
    } catch (err) {
      setResetError(errorMessage(err));
      return null;
    } finally {
      setResetting(false);
    }
  }, [res]);

  const data = res.data;
  return {
    dashboard: data,
    worker: data?.worker ?? null,
    cards: data?.cards ?? [],
    totals: data?.totals ?? null,
    /** Cards that still have money owed, biggest first. */
    owing: (data?.cards ?? []).filter((c) => c.balance > 0).sort((a, b) => b.balance - a.balance),
    loading: res.loading,
    refreshing: res.refreshing,
    error: res.error ? errorMessage(res.error) : null,
    refresh: res.refresh,
    reset,
    resetting,
    resetResult,
    resetError,
  };
}
