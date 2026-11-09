"use client";

// Safety switch. Any screen that gets a flagged `safety` result calls raise(safety) and routes to
// /safety; the Safety screen reads it back (or shows every helpline when there is none).
// quickExit() wipes this tab's session data and replaces the page with the neutral recipe page.

import { useCallback, useSyncExternalStore } from "react";
import { DEFAULT_HELPLINES, quickExit, telHref } from "@/lib/safety";
import { safetyStore } from "@/lib/store";
import type { Helpline, Safety } from "@/lib/types";

export function useSafety() {
  const { safety } = useSyncExternalStore(safetyStore.subscribe, safetyStore.get, safetyStore.getServer);

  const raise = useCallback((s: Safety) => safetyStore.set({ safety: s, at: Date.now() }), []);
  const clear = useCallback(() => safetyStore.clear(), []);

  const helplines: Helpline[] = safety?.helplines?.length ? safety.helplines : DEFAULT_HELPLINES;
  return {
    safety,
    flagged: !!safety?.flagged,
    categories: safety?.categories ?? [],
    message: safety?.message ?? null,
    /** Phone helplines first (tap to call), then web links. */
    callable: helplines.filter((h) => h.number).map((h) => ({ ...h, href: telHref(h.number!) })),
    links: helplines.filter((h) => !h.number && h.url),
    raise,
    clear,
    quickExit,
  };
}
