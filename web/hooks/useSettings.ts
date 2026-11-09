"use client";

// Remembered settings (worker, UI language, STT preset) and the translator for the UI chrome.

import { useCallback, useMemo, useSyncExternalStore } from "react";
import { translator, type Translate, type UiLang } from "@/lib/i18n";
import { settingsStore, type Settings } from "@/lib/store";
import type { ListenLang } from "@/lib/types";

const noop = () => () => {};

/** False during SSR / the first hydration pass, true after: gate anything read from storage. */
export function useHydrated(): boolean {
  return useSyncExternalStore(noop, () => true, () => false);
}

export function useSettings() {
  const settings = useSyncExternalStore(settingsStore.subscribe, settingsStore.get, settingsStore.getServer);
  const hydrated = useHydrated();
  const update = useCallback((patch: Partial<Settings>) => settingsStore.set(patch), []);
  return {
    ...settings,
    hydrated,
    /** The worker has not picked a language yet (show the picker once). */
    needsLanguage: hydrated && settings.uiLang === null,
    setUiLang: useCallback((uiLang: UiLang) => update({ uiLang }), [update]),
    setWorkerId: useCallback((workerId: number) => update({ workerId }), [update]),
    setListenLang: useCallback((listenLang: ListenLang) => update({ listenLang }), [update]),
    update,
  };
}

/** Translator for the worker's remembered language (English until she picks). */
export function useT(): { t: Translate; lang: UiLang } {
  const { uiLang } = useSettings();
  const lang = uiLang ?? "en";
  return useMemo(() => ({ t: translator(lang), lang }), [lang]);
}

/** Translator for a fixed language (the employer page uses the employer's language). */
export function useStrings(lang: UiLang): Translate {
  return useMemo(() => translator(lang), [lang]);
}
