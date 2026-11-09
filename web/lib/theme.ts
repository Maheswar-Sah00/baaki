"use client";

// Light / dark theme and colour palette, shared by the website and the app.
//   - The inline script (THEME_INIT_SCRIPT, injected in app/layout.tsx <head>) sets
//     <html data-theme data-palette> before first paint, so there is no flash.
//   - switchTheme(next, x, y) grows the new theme as a circle from (x, y) with the View
//     Transitions API (same pattern as Rastro's lib/theme.ts and Burner's theme.js); without the
//     API, or with reduced motion, it switches at once.
//   - The choice is saved in localStorage ("baaki-theme"); first visit follows prefers-color-scheme.
//   - ?theme=light|dark forces a theme for one page load (screenshots); ?palette=warm|gnani sets the
//     palette for this tab (sessionStorage) so both palettes can be previewed.

import { useSyncExternalStore } from "react";
import { flushSync } from "react-dom";

import { DEFAULT_PALETTE, PALETTE_KEY, THEME_KEY, type Palette, type Theme } from "./theme-config";

export { DEFAULT_PALETTE, type Palette, type Theme } from "./theme-config";

const REVEAL_MS = 650;

const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function readTheme(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function readPalette(): Palette {
  if (typeof document === "undefined") return DEFAULT_PALETTE;
  return document.documentElement.dataset.palette === "gnani" ? "gnani" : "warm";
}

function syncMetaColor() {
  try {
    const color = getComputedStyle(document.documentElement).getPropertyValue("--meta-bg").trim();
    document.querySelectorAll('meta[name="theme-color"]').forEach((m) => color && m.setAttribute("content", color));
  } catch {
    /* ignore */
  }
}

export function setTheme(t: Theme) {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(THEME_KEY, t);
  } catch {
    /* storage blocked: the choice lasts for this page view */
  }
  syncMetaColor();
  notify();
}

export function setPalette(p: Palette) {
  document.documentElement.dataset.palette = p;
  try {
    sessionStorage.setItem(PALETTE_KEY, p);
  } catch {
    /* ignore */
  }
  syncMetaColor();
  notify();
}

type DocWithVT = Document & {
  startViewTransition?: (cb: () => void) => { ready: Promise<void>; finished: Promise<void> };
};

/** Switch theme with a circular reveal growing from (x, y), e.g. the centre of the toggle button. */
export function switchTheme(t: Theme, x?: number, y?: number) {
  const doc = document as DocWithVT;
  const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (!doc.startViewTransition || still || typeof x !== "number" || typeof y !== "number") {
    setTheme(t);
    return;
  }
  const r = Math.ceil(Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)));
  const at = ` at ${Math.round(x)}px ${Math.round(y)}px)`;
  document.documentElement.classList.add("theme-revealing");
  const vt = doc.startViewTransition(() => flushSync(() => setTheme(t)));
  vt.ready
    .then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px${at}`, `circle(${r}px${at}`] },
        { duration: REVEAL_MS, easing: "cubic-bezier(0.4, 0, 0.2, 1)", pseudoElement: "::view-transition-new(root)" },
      );
    })
    .catch(() => {
      /* skipped (hidden tab): the theme is already set */
    });
  vt.finished.finally(() => document.documentElement.classList.remove("theme-revealing"));
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

/** Current theme; re-renders on change. Returns "light" during SSR. */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, readTheme, () => "light" as Theme);
}

export function usePalette(): Palette {
  return useSyncExternalStore(subscribe, readPalette, () => DEFAULT_PALETTE);
}
