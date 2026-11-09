import { SANDBOX_BANNER } from "@/lib/features/sandbox";
import { ShieldIcon } from "@/components/ui/icons";
import css from "./sandbox.module.css";

/** Shown on every sandbox screen: what this is, in one calm line. `compact` is the in-phone chip. */
export function Banner({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <span role="note" className={css.chip}>
        {SANDBOX_BANNER}
      </span>
    );
  }
  return (
    <div role="note" className={css.banner}>
      <span className={css.bannerIcon} aria-hidden="true">
        <ShieldIcon />
      </span>
      <span>
        <strong>{SANDBOX_BANNER}</strong> No money moves and no live AI is called.
      </span>
    </div>
  );
}
