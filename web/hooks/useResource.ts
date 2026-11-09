"use client";

// Generic "load this from the API" hook with refresh and optional polling. Used by the data hooks.

import { useCallback, useEffect, useEffectEvent, useState } from "react";
import { isAbort } from "@/lib/api";

type State<T> = { key: string | null; data: T | null; error: unknown; at: number };

export function useResource<T>(
  key: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
  opts: { pollMs?: number | null } = {},
) {
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null, at: 0 });
  const [nonce, setNonce] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const run = useEffectEvent((signal: AbortSignal) => fetcher(signal));

  useEffect(() => {
    if (key === null) return;
    const ac = new AbortController();
    run(ac.signal).then(
      (data) => {
        setState({ key, data, error: null, at: Date.now() });
        setRefreshing(false);
      },
      (error) => {
        if (isAbort(error)) return;
        setState((s) => ({ key, data: s.key === key ? s.data : null, error, at: Date.now() }));
        setRefreshing(false);
      },
    );
    return () => ac.abort();
  }, [key, nonce]);

  // Polling: only while the tab is visible.
  const pollMs = opts.pollMs ?? null;
  useEffect(() => {
    if (key === null || !pollMs) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") setNonce((n) => n + 1);
    }, pollMs);
    return () => window.clearInterval(id);
  }, [key, pollMs]);

  const refresh = useCallback(() => {
    setRefreshing(true);
    setNonce((n) => n + 1);
  }, []);

  /** Replace the data locally (e.g. with a mutation's response) without refetching. */
  const setData = useCallback(
    (data: T) => setState((s) => ({ key: s.key ?? key, data, error: null, at: Date.now() })),
    [key],
  );

  const current = state.key === key;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: key !== null && !current,
    refreshing,
    updatedAt: current ? state.at : 0,
    refresh,
    setData,
  };
}
