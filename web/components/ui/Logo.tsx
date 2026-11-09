// Baaki logo (10 Nov 2026 redesign): a flat single-colour mark, a speech bubble drawn as a "b"
// (round stem, round bowl, the tail at the bottom right, a coin-round counter), plus a Cabinet
// Grotesk bold "Baaki" wordmark and a small Telugu "బాకీ". Ink in light, white in dark: everything
// is currentColor, so it follows --text. No gradients, no glow.
// Server-safe (no hooks). Styles are inline so the mark never depends on a stylesheet; the class
// names (logo, logo-mark, logo-word, logo-te) stay as hooks for page CSS (e.g. hiding the Telugu on
// narrow headers). The PNG app icons come from scripts/make-icons.mjs (same path).

import type { CSSProperties } from "react";

/** The mark path on a 512 grid; its tight square box is MARK_VIEWBOX. Mirrored in make-icons.mjs. */
export const MARK_PATH =
  "M80 120a64 64 0 0 1 128 0V170a160 160 0 0 1 248 134V480L400 432H144a64 64 0 0 1-64-64Z M296 246a58 58 0 1 0 0.01 0Z";
export const MARK_VIEWBOX = "56 56 424 424";

const markStyle: CSSProperties = {
  display: "inline-block",
  flex: "none",
  background: "none",
  boxShadow: "none",
  borderRadius: 0,
  color: "currentColor",
};

export function LogoMark({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <span className={`logo-mark ${className ?? ""}`} style={{ ...markStyle, width: size, height: size }} aria-hidden="true">
      <svg viewBox={MARK_VIEWBOX} width={size} height={size} style={{ display: "block", width: "100%", height: "100%" }}>
        <path d={MARK_PATH} fill="currentColor" />
      </svg>
    </span>
  );
}

/**
 * `size` keeps its old meaning (the logo's height in px). The wordmark scales with it, so a 34 px
 * header logo gets a ~25 px wordmark; the mark is drawn a little smaller than `size` so it sits
 * optically with the cap height.
 */
export function Logo({ size = 36, className, telugu = true }: { size?: number; className?: string; telugu?: boolean }) {
  const mark = Math.round(size * 0.76);
  const word = Math.max(15, Math.round(size * 0.74));
  return (
    <span
      className={`logo ${className ?? ""}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: Math.round(size * 0.22),
        color: "var(--text)",
        textDecoration: "none",
        lineHeight: 1,
      }}
    >
      <LogoMark size={mark} />
      <span
        className="logo-word"
        style={{
          display: "inline-flex",
          alignItems: "baseline",
          gap: Math.round(size * 0.2),
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: word,
          letterSpacing: "-0.045em",
          lineHeight: 1,
          color: "inherit",
        }}
      >
        Baaki
        {telugu ? (
          <span
            className="logo-te"
            lang="te"
            style={{
              fontFamily: "var(--font-noto-telugu), 'Nirmala UI', sans-serif",
              fontWeight: 500,
              fontSize: Math.max(11, Math.round(word * 0.5)),
              letterSpacing: 0,
              color: "var(--muted)",
            }}
          >
            బాకీ
          </span>
        ) : null}
      </span>
    </span>
  );
}
