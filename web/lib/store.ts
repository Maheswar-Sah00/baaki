// Tiny client-side stores (no library): remembered settings in localStorage, and the hand-off
// between screens (the spoken draft, the last safety result) in sessionStorage, which the quick-exit
// wipes. Each store is a useSyncExternalStore source: subscribe + getSnapshot + getServerSnapshot.

import type { UiLang } from "./i18n";
import type { ListenLang, MeterChip, MeterSummary, Safety } from "./types";

type Listener = () => void;

function safeGet(storage: "local" | "session", key: string): string | null {
  try {
    return (storage === "local" ? window.localStorage : window.sessionStorage).getItem(key);
  } catch {
    return null;
  }
}

function safeSet(storage: "local" | "session", key: string, value: string | null) {
  try {
    const s = storage === "local" ? window.localStorage : window.sessionStorage;
    if (value === null) s.removeItem(key);
    else s.setItem(key, value);
  } catch {
    /* private mode / blocked storage: keep working in memory */
  }
}

function createStore<T>(storage: "local" | "session", key: string, initial: T) {
  let cache: T | undefined;
  let raw: string | null | undefined;
  const listeners = new Set<Listener>();

  const read = (): T => {
    if (typeof window === "undefined") return initial;
    const now = safeGet(storage, key);
    if (cache !== undefined && now === raw) return cache;
    raw = now;
    try {
      cache = now ? ({ ...initial, ...JSON.parse(now) } as T) : initial;
    } catch {
      cache = initial;
    }
    return cache;
  };

  const write = (next: T | null) => {
    const value = next === null ? null : JSON.stringify(next);
    safeSet(storage, key, value);
    raw = value;
    cache = next === null ? initial : next;
    listeners.forEach((l) => l());
  };

  return {
    get: read,
    getServer: () => initial,
    set: (patch: Partial<T>) => write({ ...read(), ...patch }),
    clear: () => write(null),
    subscribe: (l: Listener) => {
      listeners.add(l);
      const onStorage = (e: StorageEvent) => {
        if (e.key === key) l();
      };
      window.addEventListener("storage", onStorage);
      return () => {
        listeners.delete(l);
        window.removeEventListener("storage", onStorage);
      };
    },
  };
}

// ------------------------------------------------------------------ settings (remembered)
export type Settings = {
  /** Demo worker: 1 = Lakshmi (Telugu), 2 = Rafiq (Hinglish). */
  workerId: number;
  /** UI chrome language; null until she picks once. */
  uiLang: UiLang | null;
  /** STT preset for /speak. */
  listenLang: ListenLang;
};

export const DEFAULT_SETTINGS: Settings = { workerId: 1, uiLang: null, listenLang: "auto" };
export const settingsStore = createStore<Settings>("local", "baaki.settings.v1", DEFAULT_SETTINGS);

// ------------------------------------------------------------------ the spoken draft (Speak -> Confirm)
export type Draft = {
  transcript: string;
  listenLang: ListenLang;
  detectedLang: string | null;
  /** Meter chips after her edits, and the summary they total to. */
  chips: MeterChip[];
  summary: MeterSummary | null;
  chipsEdited: boolean;
  /** A draft case already created from this transcript (resume instead of creating twice). */
  caseId: number | null;
  createdAt: number;
};

export const EMPTY_DRAFT: Draft = {
  transcript: "",
  listenLang: "auto",
  detectedLang: null,
  chips: [],
  summary: null,
  chipsEdited: false,
  caseId: null,
  createdAt: 0,
};
export const draftStore = createStore<Draft>("session", "baaki.draft.v1", EMPTY_DRAFT);

// ------------------------------------------------------------------ last safety result
export type SafetyState = { safety: Safety | null; at: number };
export const safetyStore = createStore<SafetyState>("session", "baaki.safety.v1", { safety: null, at: 0 });

/** Quick exit: forget everything sensitive in this tab. */
export function wipeSession() {
  draftStore.clear();
  safetyStore.clear();
  try {
    window.sessionStorage.clear();
  } catch {
    /* ignore */
  }
}
