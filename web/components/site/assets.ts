// Server-only helper: which photo slots already have a file in /public/assets. The site renders a
// photo <AssetSlot> only for those, and a designed canvas otherwise, so a missing photo never 404s
// in the browser. Static pages evaluate this at build time: add the .webp and rebuild.

import { existsSync } from "node:fs";
import { join } from "node:path";

/** Slot names on "/" ("What Baaki can do"). Prompts: docs/assets/site.md. */
export const CAN_DO_SLOTS = [
  "can-do-wage-check",
  "can-do-letter-voice",
  "can-do-promise-keeper",
  "can-do-evidence-inbox",
  "can-do-haq-raise",
  "can-do-exit-kit",
] as const;

/** Every illustration the home page can show (the can-do cards plus the section art). */
export const SITE_SLOTS = [...CAN_DO_SLOTS, "cast-trio", "ill-speak", "ill-celebrate", "check-payday-envelope"] as const;

export function existingAssets(names: readonly string[], ext = "webp"): string[] {
  return names.filter((n) => {
    try {
      return existsSync(join(process.cwd(), "public", "assets", `${n}.${ext}`));
    } catch {
      return false;
    }
  });
}
