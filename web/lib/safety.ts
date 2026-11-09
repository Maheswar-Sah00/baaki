// Safety constants that must work even with no backend: the helplines and the quick exit.

import type { Helpline } from "./types";
import { wipeSession } from "./store";

/** Mirrors backend/app/safety.py HELPLINES. */
export const DEFAULT_HELPLINES: Helpline[] = [
  { number: "112", name: "Emergency (police, ambulance)", for: ["locked_in", "violence", "trafficking"] },
  { number: "181", name: "Women Helpline", for: ["violence", "harassment", "locked_in", "id_taken"] },
  { number: "1098", name: "Childline", for: ["minor", "trafficking"] },
  { number: "1800 833 9020", name: "India Labourline (work and wage problems, Hyderabad desk)", for: ["id_taken"] },
  { number: null, name: "NDWM (National Domestic Workers Movement)", url: "https://ndwm.org", for: [] },
];

export function telHref(number: string): string {
  return `tel:${number.replace(/[^\d+]/g, "")}`;
}

/** The neutral page the quick exit lands on. */
export const QUICK_EXIT_PATH = "/r";

/**
 * Quick exit: wipe this tab's session data, then replace the current history entry with the
 * neutral recipe page (so Back does not return here). The recipe page also overwrites the entry.
 */
export function quickExit() {
  wipeSession();
  // Drop the service worker's offline copies of cases and voice notes (public/sw.js).
  try {
    navigator.serviceWorker?.controller?.postMessage({ type: "wipe" });
    void caches?.keys().then((keys) => keys.filter((k) => /^baaki-(api|media|pages)-/.test(k)).forEach((k) => void caches.delete(k)));
  } catch {
    /* ignore */
  }
  try {
    window.history.replaceState(null, "", QUICK_EXIT_PATH);
  } catch {
    /* ignore */
  }
  window.location.replace(QUICK_EXIT_PATH);
}
